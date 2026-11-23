//! Leave one physical core free for the rest of the machine while the docs embedding worker runs: the process may use
//! every other core, and embeds with one thread per core it may use. On a hybrid Intel CPU the free core is a Performance
//! core (the highest efficiency class), so the desktop stays responsive; on CPUs with one class it is the first core.

/// Pin this process off one physical core and return how many physical cores it keeps, or None when the topology
/// cannot be read or there is nothing to spare (one core).
pub(crate) fn spare_one() -> Option<usize> {
    let (keep, cores) = keep_mask(&cores()?)?;
    set_affinity(keep).then_some(cores)
}

/// From `(efficiency class, logical-processor mask)` per physical core: the mask without the first core of the highest
/// class, and the number of cores left.
fn keep_mask(cores: &[(u8, usize)]) -> Option<(usize, usize)> {
    let top = cores.iter().map(|c| c.0).max()?;
    let spared = cores.iter().find(|c| c.0 == top)?.1;
    let all = cores.iter().fold(0, |m, c| m | c.1);
    (cores.len() > 1).then_some((all & !spared, cores.len() - 1))
}

#[cfg(windows)]
fn cores() -> Option<Vec<(u8, usize)>> {
    use windows_sys::Win32::System::SystemInformation::{
        GetLogicalProcessorInformationEx, RelationProcessorCore,
        SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX,
    };
    let mut len = 0u32;
    // SAFETY: a null buffer with length 0 only asks for the size needed.
    unsafe {
        GetLogicalProcessorInformationEx(RelationProcessorCore, std::ptr::null_mut(), &mut len)
    };
    let mut buf = vec![0u64; (len as usize).div_ceil(8)]; // u64: the records need 8-byte alignment
    // SAFETY: `buf` holds at least `len` bytes, the size the first call asked for.
    let ok = unsafe {
        GetLogicalProcessorInformationEx(RelationProcessorCore, buf.as_mut_ptr().cast(), &mut len)
    };
    if ok == 0 {
        return None;
    }
    let (mut out, mut at) = (Vec::new(), 0usize);
    while at < len as usize {
        // SAFETY: Windows wrote `len` bytes of back-to-back records, each `Size` bytes long, starting at an aligned buffer.
        let info = unsafe {
            &*(buf.as_ptr().cast::<u8>().add(at) as *const SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)
        };
        // SAFETY: RelationProcessorCore records carry the Processor variant.
        let core = unsafe { &info.Anonymous.Processor };
        let group = core.GroupMask[0];
        if group.Group != 0 {
            return None; // shortcut: more than 64 logical processors span groups; one affinity mask cannot cover them
        }
        out.push((core.EfficiencyClass, group.Mask));
        at += info.Size as usize;
    }
    Some(out)
}

#[cfg(windows)]
fn set_affinity(mask: usize) -> bool {
    use windows_sys::Win32::System::Threading::{GetCurrentProcess, SetProcessAffinityMask};
    // SAFETY: the pseudo-handle of this process and a mask of processors that exist.
    unsafe { SetProcessAffinityMask(GetCurrentProcess(), mask) != 0 }
}

// shortcut: Windows only (the supported platform); elsewhere the worker keeps the default thread count.
#[cfg(not(windows))]
fn cores() -> Option<Vec<(u8, usize)>> {
    None
}

#[cfg(not(windows))]
fn set_affinity(_: usize) -> bool {
    false
}

#[cfg(test)]
mod tests {
    use super::keep_mask;

    #[test]
    fn spares_the_first_performance_core() {
        // 12-core AMD with SMT: one class, cores own processor pairs; core 0 (processors 0 and 1) is spared.
        let amd: Vec<(u8, usize)> = (0..12).map(|i| (0, 0b11 << (2 * i))).collect();
        assert_eq!(keep_mask(&amd), Some(((1 << 24) - 1 - 0b11, 11)));
        // Hybrid Intel listed E-cores first: the first P-core (class 1, processors 4 and 5) is spared.
        let hybrid = [
            (0, 1),
            (0, 2),
            (0, 4),
            (0, 8),
            (1, 0b11 << 4),
            (1, 0b11 << 6),
        ];
        assert_eq!(keep_mask(&hybrid), Some((0b1100_1111, 5)));
        assert_eq!(keep_mask(&[(0, 1)]), None, "one core: nothing to spare");
        assert_eq!(keep_mask(&[]), None);
    }
}
