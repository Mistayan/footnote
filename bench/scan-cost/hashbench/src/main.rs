//! BLAKE3 against SHA-256 on the files of a share (issue #549, `bench/experiments/SCAN-COST-2026-11-23.md`).
//!
//! `cargo run --release -- SHARE [RUNS]`: each file is read into memory (not timed), then hashed with SHA-256
//! (`sha2` 0.10, as the engine does), BLAKE3 on one thread and BLAKE3 multi-threaded per file (`update_rayon`).
//! Prints one JSON line per run with the summed hash time of each algorithm.
use sha2::{Digest, Sha256};
use std::time::{Duration, Instant};

const EXTS: [&str; 9] = [
    "md", "txt", "pdf", "png", "jpg", "jpeg", "webp", "tiff", "bmp",
];

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let share = args.get(1).expect("usage: hashbench SHARE [RUNS]");
    let runs: usize = args.get(2).map_or(3, |s| s.parse().expect("RUNS"));
    let mut files = Vec::new();
    for e in walkdir::WalkDir::new(share).sort_by_file_name() {
        let e = e.expect("walk");
        let ext = e
            .path()
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_lowercase();
        if e.file_type().is_file() && EXTS.contains(&ext.as_str()) {
            files.push(e.into_path());
        }
    }
    for run in 1..=runs {
        let (mut sha, mut b1, mut bn) = (Duration::ZERO, Duration::ZERO, Duration::ZERO);
        let mut bytes = 0_u64;
        let mut check = 0_u8; // keeps the digests observable so nothing is optimised away
        for p in &files {
            let data = std::fs::read(p).expect("read");
            bytes += data.len() as u64;
            let t = Instant::now();
            check ^= Sha256::digest(&data)[0];
            sha += t.elapsed();
            let t = Instant::now();
            check ^= blake3::hash(&data).as_bytes()[0];
            b1 += t.elapsed();
            let t = Instant::now();
            check ^= blake3::Hasher::new()
                .update_rayon(&data)
                .finalize()
                .as_bytes()[0];
            bn += t.elapsed();
        }
        let ms = |d: Duration| d.as_secs_f64() * 1000.0;
        let gib_s = |d: Duration| bytes as f64 / 1073741824.0 / d.as_secs_f64();
        println!(
            "{{\"run\":{run},\"files\":{},\"bytes\":{bytes},\"sha256_ms\":{:.1},\"blake3_ms\":{:.1},\"blake3_rayon_ms\":{:.1},\"sha256_gib_s\":{:.2},\"blake3_gib_s\":{:.2},\"blake3_rayon_gib_s\":{:.2},\"threads\":{},\"check\":{check}}}",
            files.len(),
            ms(sha),
            ms(b1),
            ms(bn),
            gib_s(sha),
            gib_s(b1),
            gib_s(bn),
            std::thread::available_parallelism().map_or(0, |n| n.get())
        );
    }
}
