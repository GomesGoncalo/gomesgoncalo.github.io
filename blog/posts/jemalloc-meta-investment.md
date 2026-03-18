---
title: Benchmarking jemalloc in my Real-World Environment
date: 2026-03-17
draft: true
description: With the recent news about making more developments in jemalloc I had a look at how it currently performs in the applications I am writing and using on a daily basis.
tags: [allocators, jemalloc, rust, cpp, benchmarking]
---

## What is jemalloc?

[jemalloc](https://jemalloc.net/) is a malloc implementation that focuses on fragmentation.
Recently, there have been [news](https://engineering.fb.com/2026/03/02/data-infrastructure/investing-in-infrastructure-metas-renewed-commitment-to-jemalloc/) about Meta's investment in the project
and I thought it'd be interesting to look into the software I develop
and use on a daily basis.

## Why Memory Allocation Matters

Depending on your application's allocation patterns, different allocators may
lead to fragmentation, which can cause performance degradation and
increased memory usage.

For applications with heavy allocation and deallocation, a well-designed
allocator can significantly improve performance; however a poorly designed
one may cause fragmentation, leading to increased memory usage and degraded
performance.

When the allocation patterns are more predictable, the choice of allocator may
be less critical, but it can still impact performance and memory usage.

## How jemalloc Works

<!-- TODO: expand each bullet into prose -->
- **Arena-based design**: thread-local arenas reduce lock contention compared to a single global heap lock (ptmalloc2's approach)
- **Size-class segregation**: allocations are bucketed into discrete size classes, reducing internal fragmentation
- **Extent management and dirty page decay**: jemalloc tracks extents (contiguous memory ranges) and returns dirty pages to the OS on a configurable decay timer, keeping RSS low over time
- **Differences from alternatives**: ptmalloc2 (glibc default) uses per-thread arenas but lacks jemalloc's fine-grained size classes; tcmalloc (Google) focuses on throughput over fragmentation

## Meta's Investment — What Changed

<!-- TODO: read https://engineering.fb.com/2026/03/02/data-infrastructure/investing-in-infrastructure-metas-renewed-commitment-to-jemalloc/ carefully -->
<!-- Summarise: new maintainers? concrete roadmap items? specific fragmentation improvements? -->
<!-- Why a large company investing matters for open-source infrastructure -->

## Testing It on My Own Software

The test subject is [`discord-overlay`](https://github.com/GomesGoncalo/discord-overlay),
a voice channel overlay I wrote for Hyprland. Electron-based overlays don't work under
the Wayland layer-shell protocol, so I built one in Rust using EGL/GLES2 — it shows
participants, speaking status, and mute/deafen controls via the Discord IPC socket.

It is a long-running, event-driven process: mostly idle, waking on Discord IPC events
and Wayland frame callbacks. This makes it an interesting allocator test case because
allocation pressure is low but sustained — exactly the regime where fragmentation
accumulates quietly.

### Methodology

Swapping allocators required no recompilation. jemalloc was injected at runtime via
`LD_PRELOAD`, which interposes its `malloc`/`free` symbols before glibc's:

```bash
LD_PRELOAD=/usr/lib/libjemalloc.so.2 hypr-overlay-wl
```

Both runs used the same binary. The process was then profiled with
[heaptrack](https://github.com/KDE/heaptrack), attached to the running PID after
enabling ptrace:

```bash
echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
heaptrack --pid $(pgrep hypr-overlay-wl)
```

### Results

| Metric | glibc (ptmalloc2) | jemalloc | Delta |
|---|---|---|---|
| Runtime | 17.02 s | 15.34 s | — |
| Alloc calls/s | 4,521 | 4,905 | +8.5% |
| Temporary allocs/s | 1,564 | 1,726 | +10.4% |
| Peak heap | 154.70 KB | 138.55 KB | **−10.4%** |
| Peak RSS | 177.24 MB | 209.52 MB | **+18.2%** |
| Leaked | 114.15 KB | 97.78 KB | −14.3% |

The runtimes differ because these were live sessions of different lengths, not
controlled identical workloads — throughput figures (per-second rates) are the
meaningful comparison.

jemalloc reduces peak heap consumption by 10% and leaked memory by 14%, confirming
better fragmentation control. Allocation throughput is marginally higher. However,
peak RSS increases by 18% — jemalloc pre-allocates thread arenas at startup and
maps them eagerly from the OS. For a session this short (15–17 s), the dirty page
decay timer (default: 10 s muzzy, 5 s dirty) had barely had time to return pages,
so more address space was mapped than actively needed. In a longer-running session
the RSS gap would likely narrow.

## A Synthetic Benchmark: Where jemalloc Actually Wins

The `discord-overlay` results are honest but modest — a single-threaded, event-driven
process with low allocation pressure is not where allocator design matters most. To
find the conditions where jemalloc pulls ahead, I ran a synthetic benchmark: 8 threads
each allocating 50,000 objects across a range of sizes (8 B to 4 KB), freeing every
other one to create holes, then re-allocating into the fragmented heap.

```rust
use std::thread;
use std::hint::black_box;

fn main() {
    let handles: Vec<_> = (0..8).map(|_| {
        thread::spawn(|| {
            let sizes = [8usize, 16, 32, 64, 128, 256, 512, 1024, 4096];
            let mut allocs: Vec<Vec<u8>> = (0..50_000)
                .map(|i| vec![0u8; sizes[i % sizes.len()]])
                .collect();
            let mut i = 0;
            allocs.retain(|_| { i += 1; i % 2 == 0 });
            for i in 0..25_000 {
                allocs.push(black_box(vec![1u8; sizes[i % sizes.len()]]));
            }
            black_box(allocs);
        })
    }).collect();
    handles.into_iter().for_each(|h| h.join().unwrap());
}
```

Profiled with heaptrack under the same `LD_PRELOAD` methodology:

| Metric | glibc (ptmalloc2) | jemalloc | Delta |
|---|---|---|---|
| Runtime | 0.54 s | 0.26 s | **−52% (2× faster)** |
| Alloc calls/s | 1,103,110 | 2,316,957 | **+110% throughput** |
| Temporary allocs | 279 | 44 | **−84%** |
| Peak heap | 245.00 MB | 232.80 MB | −5% |
| Peak RSS | 296.39 MB | 286.28 MB | −3.4% |

jemalloc is **twice as fast** under 8-thread contention. This is jemalloc's arena design
in action: each thread gets its own arena, so `malloc` and `free` calls never wait on
each other. ptmalloc2 serialises threads on a shared lock under pressure — that
serialisation is the 0.28 s gap.

The temporary allocation count dropping from 279 to 44 is also telling: jemalloc
recycles short-lived allocations through its thread-local cache far more aggressively,
avoiding round-trips to the OS.

## Two Workloads, Two Different Answers

These two datasets tell complementary stories about when allocator choice matters.

For `discord-overlay` — a single-threaded, event-driven Wayland process making around
4,500 allocation calls per second — the difference between glibc and jemalloc is
negligible for throughput and modest for fragmentation. The RSS is actually higher with
jemalloc due to eager arena pre-allocation. If your application looks like this, the
system allocator is fine.

For a multi-threaded workload with concurrent allocation pressure across many threads,
jemalloc wins decisively: 2× runtime improvement and 110% more allocation throughput.
If your application spawns thread pools, handles concurrent requests, or does
parallelised data processing, jemalloc (or tcmalloc) is worth reaching for.

The rule of thumb: **thread count is the primary signal**. A single-threaded or
lightly-threaded program will see little benefit; a program that allocates heavily
across many threads will see substantial gains.

## Risks and Caveats

- **Higher RSS in short sessions**: jemalloc pre-allocates thread arenas eagerly and
  returns dirty pages to the OS on a decay timer (default: 5 s dirty, 10 s muzzy). A
  process that runs for only a few seconds may show higher RSS than glibc even if
  long-run fragmentation is lower — the `discord-overlay` results above demonstrate this.

- **Rust global allocator conflict**: only one `#[global_allocator]` can be set per
  binary. If a dependency also tries to set one, the build fails. `tikv-jemallocator`
  is the maintained crate for using jemalloc as the Rust global allocator.

- **Profiling overhead**: `MALLOC_CONF` options such as `prof:true` add non-trivial
  overhead. Keep profiling builds separate from production.

- **Compatibility**: musl libc, some sanitizer builds, and statically linked binaries
  have known issues with jemalloc. Check upstream before adopting in CI pipelines.

## Conclusion and Future Outlook

<!-- TODO: write once Meta blog post is read and remaining sections are filled -->
<!-- Points to cover:
     - Meta's renewed investment and what it means for the project's longevity
     - When to reach for jemalloc vs sticking with the system allocator
     - Future tooling improvements on the roadmap
-->
