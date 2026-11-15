//! What the machine offers for embedding models: CPU threads, RAM, GPUs with their dedicated memory, from any vendor.
//! Windows: the display adapters' registry keys (the driver's 64-bit memory size; WMI caps VRAM at 4 GB). Linux: /proc and
//! /sys/class/drm. macOS: RAM only for now.
use serde_json::{Value, json};

pub fn detect() -> Value {
    let gpus = gpus();
    json!({
        "cpu_threads": std::thread::available_parallelism().map_or(0, usize::from),
        "ram_bytes": ram_bytes(),
        "gpus": gpus,
    })
}

#[cfg(windows)]
fn ram_bytes() -> Option<u64> {
    use windows_sys::Win32::System::SystemInformation::{GlobalMemoryStatusEx, MEMORYSTATUSEX};
    let mut m: MEMORYSTATUSEX = unsafe { std::mem::zeroed() };
    m.dwLength = std::mem::size_of::<MEMORYSTATUSEX>() as u32;
    (unsafe { GlobalMemoryStatusEx(&mut m) } != 0).then_some(m.ullTotalPhys)
}

#[cfg(target_os = "linux")]
fn ram_bytes() -> Option<u64> {
    let info = std::fs::read_to_string("/proc/meminfo").ok()?;
    let kb: u64 = info
        .lines()
        .find(|l| l.starts_with("MemTotal:"))?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()?;
    Some(kb * 1024)
}

#[cfg(not(any(windows, target_os = "linux")))]
fn ram_bytes() -> Option<u64> {
    let out = std::process::Command::new("sysctl")
        .args(["-n", "hw.memsize"])
        .output()
        .ok()?;
    String::from_utf8(out.stdout).ok()?.trim().parse().ok()
}

#[cfg(windows)]
fn gpus() -> Vec<Value> {
    use windows_sys::Win32::System::Registry::{
        HKEY_LOCAL_MACHINE, RRF_RT_REG_BINARY, RRF_RT_REG_DWORD, RRF_RT_REG_QWORD, RRF_RT_REG_SZ,
        RegGetValueW,
    };
    let wide = |s: &str| s.encode_utf16().chain(Some(0)).collect::<Vec<u16>>();
    // Display adapters class; one numbered subkey per adapter.
    const CLASS: &str =
        r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}";
    let mut out = Vec::new();
    for i in 0..16 {
        let key = wide(&format!(r"{CLASS}\{i:04}"));
        let mut name = [0u16; 256];
        let mut size = std::mem::size_of_val(&name) as u32;
        let found = unsafe {
            RegGetValueW(
                HKEY_LOCAL_MACHINE,
                key.as_ptr(),
                wide("DriverDesc").as_ptr(),
                RRF_RT_REG_SZ,
                std::ptr::null_mut(),
                name.as_mut_ptr().cast(),
                &mut size,
            )
        } == 0;
        if !found {
            continue;
        }
        let name = String::from_utf16_lossy(&name[..(size as usize / 2).saturating_sub(1)]);
        let mut vram = None;
        for (value, flags) in [
            (
                "HardwareInformation.qwMemorySize",
                RRF_RT_REG_QWORD | RRF_RT_REG_BINARY,
            ),
            (
                "HardwareInformation.MemorySize",
                RRF_RT_REG_DWORD | RRF_RT_REG_BINARY,
            ),
        ] {
            let mut bytes = [0u8; 8];
            let mut size = 8u32;
            let ok = unsafe {
                RegGetValueW(
                    HKEY_LOCAL_MACHINE,
                    key.as_ptr(),
                    wide(value).as_ptr(),
                    flags,
                    std::ptr::null_mut(),
                    bytes.as_mut_ptr().cast(),
                    &mut size,
                )
            } == 0;
            if ok {
                vram = Some(u64::from_le_bytes(bytes));
                break;
            }
        }
        out.push(json!({"name": name, "vram_bytes": vram}));
    }
    out
}

#[cfg(target_os = "linux")]
fn gpus() -> Vec<Value> {
    let Ok(entries) = std::fs::read_dir("/sys/class/drm") else {
        return vec![];
    };
    let mut out = Vec::new();
    for e in entries.flatten() {
        let name = e.file_name().to_string_lossy().to_string();
        if !name.starts_with("card") || name.contains('-') {
            continue; // card0, not its connectors (card0-HDMI-A-1)
        }
        let dev = e.path().join("device");
        let read = |f: &str| {
            std::fs::read_to_string(dev.join(f))
                .ok()
                .map(|s| s.trim().to_string())
        };
        let vendor = match read("vendor").as_deref() {
            Some("0x1002") => "AMD",
            Some("0x10de") => "NVIDIA",
            Some("0x8086") => "Intel",
            _ => "unknown vendor",
        };
        // AMD and Intel drivers expose dedicated memory here; NVIDIA's proprietary driver does not.
        let vram = read("mem_info_vram_total").and_then(|s| s.parse::<u64>().ok());
        out.push(json!({"name": format!("{vendor} GPU ({name})"), "vram_bytes": vram}));
    }
    out
}

#[cfg(not(any(windows, target_os = "linux")))]
fn gpus() -> Vec<Value> {
    vec![]
}
