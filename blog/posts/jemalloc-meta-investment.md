---
title: Benchmarking jemalloc in my Real-World Environment
date: 2026-03-17
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

## jemalloc's Unique Features

## Meta Investment in jemalloc

## jemalloc in my Real-World Environment

With jemalloc:

```bash
1454210 ggomes      20   0 1254M  190M  140M S   0.0  0.7  0:00.07 hypr-overlay-wl
```

and without jemalloc:

```bash
1456043 ggomes      20   0 1154M  168M  140M S   0.0  0.6  0:00.05 hypr-overlay-wl
```

## Risks?

## Future Outlook for jemalloc
