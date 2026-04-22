---
title: "EnvSync CLI — Keep Your Dev Environments in Sync"
date: 2026-04-22
draft: false
description: A Rust CLI that syncs environment variables across machines using peer-to-peer networking and CRDTs — no central server, no SaaS, encrypted at rest.
tags: [rust, cli, devtools, env, p2p]
---

## TL;DR

`envsync-cli` is a Rust CLI that syncs environment variables across machines using [iroh](https://iroh.computer/) for peer-to-peer QUIC networking and [Automerge](https://automerge.org/) for CRDT-based conflict-free merging. No central server, no third-party dependency for your secrets. Run `serve` on one machine, connect from another, and your envs stay in sync — encrypted at rest.

## Introduction

Every developer has been there: your API keys live in `.env` on your laptop, CI gets its own copies via secrets, and your desktop machine has yet another set — probably slightly out of date. You update one, forget the others, and spend an afternoon debugging why staging works but local doesn't.

I wanted something simple. Not a SaaS vault. Not another `.env` file shuffled around over Slack. Just a CLI I could run on my own machines that would keep environments consistent without needing to trust a third party with my secrets.

So I built `envsync-cli`.

## The Problem

- **Environment drift across machines**: You update `DATABASE_URL` on your work laptop but forget your home desktop. Debugging sessions become archaeology digs.
- **Secrets scattered across files and services**: One project can easily end up with envs split across `.env`, a secrets manager, GitHub Secrets, and a teammate's notes — all slightly different.
- **Onboarding friction**: Getting a new machine or new team member set up requires manually copying sensitive values, usually over channels that weren't designed for it.

## What EnvSync CLI Solves

`envsync-cli` is a peer-to-peer environment variable syncing tool. One machine runs a persistent server, and any other machine can connect to it to read or write variables. Env vars are organized into **profiles** (e.g., `global`, `work`, `personal`), can be fetched individually, or injected directly into a spawned shell or command.

There is no central server to run, no account to create, and no data leaving your network unless you intentionally run the server on a remote machine. The stored document is encrypted at rest.

### Goals

- Keep envs consistent across devices and CI
- Provide encrypted-at-rest, passphrase-based secret handling
- Make automation and onboarding reliable without a SaaS dependency

## Key Features

- **Peer-to-peer sync** via [iroh](https://iroh.computer/) — QUIC-based, NAT-traversing, no relay required
- **CRDT-based conflict resolution** using [Automerge](https://automerge.org/) — concurrent writes from multiple machines merge automatically
- **Profiles / namespaces** — organize variables into named groups (`global`, `work`, `ci`, etc.)
- **Encrypted at rest** — Argon2 key derivation + XChaCha20Poly1305; keys zeroized after every use
- **Shell injection** — `execute` syncs vars then spawns a shell or command with them already set
- **In-memory or file-backed storage** — ephemeral sessions or persistent across reboots

## How It Works

### Architecture

`envsync-cli` has a simple server/client model built entirely on peer-to-peer primitives:

- **Server** (`envsync-cli serve`): Any machine can act as the source of truth. It binds an iroh endpoint and prints a stable **Endpoint ID** you use to connect from other machines.
- **Client** (all other commands — `get`, `set`, `execute`, `list`, `delete`): Each command connects to the server, syncs the Automerge document, performs its operation, and disconnects.
- **Storage**: The server stores the document as an encrypted blob on disk at `~/.config/envsync-cli/doc.automerge`, or in memory for ephemeral sessions.

### Data Flow

1. **Server starts** → decrypts and loads the Automerge document from disk (or creates a fresh one), binds an iroh/QUIC endpoint, prints the Endpoint ID.
2. **Client connects** → opens a QUIC connection to the server using the Endpoint ID.
3. **Sync** → client and server exchange Automerge sync messages in a loop until both sides have the same document state.
4. **Mutation** (e.g., `set`) → client writes its change into its local document copy, then syncs back to the server.
5. **Server saves** → on every accepted sync, the server re-encrypts and atomically writes the document to disk (write to `.tmp`, then rename).

Conflict resolution is handled by Automerge. If two machines write to the same key concurrently, the CRDT merge picks a winner deterministically — no manual intervention needed.

## Quickstart

### Install

```bash
cargo install envsync-cli
```

### Start the server

Run this on your primary machine. It will prompt for a passphrase used to encrypt the document at rest:

```bash
envsync-cli serve file
# Passphrase: ••••••••
# Running
# Endpoint Id: <your-endpoint-id>
```

Copy the Endpoint ID — you will need it from other machines. For an ephemeral session with no disk persistence:

```bash
envsync-cli serve memory
```

### Set variables

```bash
# Set a variable in the global profile (default)
envsync-cli set DATABASE_URL postgres://localhost/myapp --remote-id <endpoint-id>

# Set a variable in a named profile
envsync-cli set API_KEY secret123 --profile work --remote-id <endpoint-id>
```

### Get and list variables

```bash
envsync-cli get DATABASE_URL --remote-id <endpoint-id>
envsync-cli list keys --remote-id <endpoint-id>
envsync-cli list keys --profile work --remote-id <endpoint-id>
envsync-cli list profiles --remote-id <endpoint-id>
```

### Execute a command with injected envs

```bash
# Drop into an interactive shell with all global vars set
envsync-cli execute --remote-id <endpoint-id>

# Run a specific command with vars from the "work" profile (merged with global)
envsync-cli execute --profile work --remote-id <endpoint-id> -- make build

# Use only the "work" profile, ignoring global vars
envsync-cli execute --profile work --exclusive --remote-id <endpoint-id> -- ./run.sh
```

## Avoiding Repeated Flags

There is no config file — `envsync-cli` is driven entirely by CLI flags. To avoid repeating `--remote-id` on every invocation, set the `IROH_REMOTE_ID` environment variable:

```bash
export IROH_REMOTE_ID=<your-endpoint-id>

envsync-cli get DATABASE_URL
envsync-cli execute -- make test
```

## CI Integration Example

Set `IROH_REMOTE_ID` as a repository secret and use `execute` to inject env vars into your build steps:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      IROH_REMOTE_ID: ${{ secrets.IROH_REMOTE_ID }}
    steps:
      - uses: actions/checkout@v4

      - name: Install envsync-cli
        run: cargo install envsync-cli

      - name: Run tests with synced envs
        run: envsync-cli execute --profile ci -- cargo test
```

> **Note**: The server must be reachable from your CI runner. iroh uses QUIC and can traverse many NATs, but a publicly addressable server (e.g., a small VPS) is the most reliable setup for CI.

## Security & Design Decisions

- **Encryption algorithm**: XChaCha20Poly1305 with a 16-byte random salt (Argon2 key derivation) and a 24-byte random nonce per write. Every save to disk produces a different ciphertext even for identical data.
- **Key hygiene**: Derived keys live in stack-allocated `[u8; 32]` arrays and are explicitly zeroized with the `zeroize` crate immediately after use.
- **No passphrase storage**: The passphrase is read at startup via `rpassword` and never touches disk.
- **Transport security**: iroh uses QUIC with TLS. All traffic between client and server is encrypted in transit.
- **Magic bytes**: The encrypted file is prefixed with `ENVSYNC1` to quickly detect corrupt or misidentified files before attempting decryption.
- **Atomic writes**: The server writes to a `.tmp` file and then renames it into place, ensuring a crash mid-write never leaves a partially written document.

Encryption is enabled by default for the `file` backend. You can disable it with `--encryption false`, but that is not recommended for anything sensitive.

## Performance & Limits

`envsync-cli` is designed for developer workflows, not high-throughput pipelines:

- **Sync latency**: Typically sub-second on a LAN. Over the internet, it depends on network conditions, but Automerge sync diffs are small for typical env var workloads.
- **Document size**: Automerge documents accumulate history over time. For dozens to hundreds of env vars this is negligible. `Automerge::save()` already compacts the representation, keeping file sizes small.
- **Concurrency**: The server accepts multiple simultaneous connections, each handled in their own async task.

## Contribution & License

Contributions are welcome. The workflow is simple:

1. Fork the repo on [GitHub](https://github.com/GomesGoncalo/envsync)
2. Make your changes in a feature branch
3. Open a pull request with a description of what changed and why

`envsync-cli` is licensed under the MIT License.

## Try It

If env var drift has cost you time, give `envsync-cli` a try:

```bash
cargo install envsync-cli
```

Star the repo on [GitHub](https://github.com/GomesGoncalo/envsync), open an issue if something is broken, or send a PR if you want to help. Feedback is always welcome.
