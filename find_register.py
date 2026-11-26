

import argparse
import struct
import time


def f32(a, b):
    try:
        return struct.unpack(">f", struct.pack(">HH", a, b))[0]
    except Exception:
        return None


def signed16(u):
    return u - 65536 if u >= 32768 else u


def encodings(hi, lo):
    s = signed16(hi)
    return {
        "float_BE": f32(hi, lo),
        "float_swap": f32(lo, hi),
        "int": float(hi),
        "int/10": hi / 10.0,
        "int/100": hi / 100.0,
        "signed/10": s / 10.0,
    }


def _unit_kwarg(fn, unit):
    import inspect
    params = inspect.signature(fn).parameters
    if "device_id" in params:
        return {"device_id": unit}
    return {"slave": unit}


def read_block(client, start, count, unit):
    out = {}
    addr = start
    end = start + count
    unit_kw = _unit_kwarg(client.read_holding_registers, unit)
    while addr < end:
        try:
            rr = client.read_holding_registers(address=addr, count=2, **unit_kw)
            if not rr.isError():
                out[addr] = (rr.registers[0], rr.registers[1])
        except Exception:
            pass
        addr += 2
    return out


def looks_like_gas(values, max_gas):
    
    if any(v is None for v in values):
        return False
    if any(abs(v) > max_gas for v in values):
        return False
    spread = max(values) - min(values)
    span = max(abs(v) for v in values) + 1.0
    if spread == 0:
        return False                      # didn't change -> not live
    # gentle drift: the change should be a modest fraction of the magnitude,
    # and not a huge absolute jump
    if spread > 0.5 * span and spread > 5.0:
        return False                      # too jumpy -> probably not a concentration
    return True


def watch(client, args):
    total = args.samples * args.delay
    print(f"Watching {args.host} registers {args.start}..{args.start+args.count-1}.")
    print(f"{args.samples} samples, {args.delay}s apart (~{total:.0f}s total). Please wait...\n")

    samples = []
    for i in range(args.samples):
        samples.append(read_block(client, args.start, args.count, args.unit))
        print(f"  sample {i+1}/{args.samples} taken")
        if i < args.samples - 1:
            time.sleep(args.delay)
    print()

    common = set(samples[0])
    for s in samples[1:]:
        common &= set(s)

    # for each register, find encodings that look gas-like across samples
    candidates = []  # (addr, encoding_name, [values])
    for addr in sorted(common):
        for name in ["float_BE", "float_swap", "int/100", "int/10", "signed/10", "int"]:
            vals = []
            ok = True
            for s in samples:
                hi, lo = s[addr]
                v = encodings(hi, lo)[name]
                vals.append(v)
            if looks_like_gas(vals, args.max_gas):
                candidates.append((addr, name, vals))
                break  # one encoding per register is enough

    if not candidates:
        print("No gas-like register found. Try: --samples 8 --delay 10 (longer),")
        print("a bigger --count, --base 1, or raise --max-gas if your values are")
        print("large. Make sure the instruments are actually measuring.")
        return

    print(f"{len(candidates)} candidate measurement register(s):\n")
    print(f"{'reg':>5} | {'encoding':>10} | values across samples | {'match?':>8}")
    print("-" * 78)
    for addr, name, vals in candidates:
        reg_shown = addr + args.base
        vals_s = ", ".join(f"{v:.3f}" for v in vals)
        match = ""
        if args.display:
            for d in args.display:
                if any(abs(v - d) <= max(abs(d) * 0.1, 0.3) for v in vals):
                    match = f"~{d}"
                    break
        print(f"{reg_shown:>5} | {name:>10} | {vals_s} | {match:>8}")

    print("\nThe rows marked under 'match?' line up with your display values.")
    print("Send me this table plus which gas each display value was.")


def _read_reg_table(read_fn, prefix, start, count, unit):
    """Read 16-bit registers across [start, start + count) using read_fn."""
    out = {}
    end = start + count
    addr = start
    unit_kw = _unit_kwarg(read_fn, unit)
    while addr < end:
        chunk = min(64, end - addr)
        try:
            rr = read_fn(address=addr, count=chunk, **unit_kw)
            if not rr.isError():
                for i, val in enumerate(rr.registers):
                    out[f"{prefix}:{addr + i}"] = val
                addr += chunk
                continue
        except TypeError:
            raise
        except Exception:
            pass

        # Fallback to single-register reads if a block contains unmapped addresses
        for sub in range(addr, addr + chunk):
            try:
                rr = read_fn(address=sub, count=1, **unit_kw)
                if not rr.isError():
                    out[f"{prefix}:{sub}"] = rr.registers[0]
            except TypeError:
                raise
            except Exception:
                pass
        addr += chunk
    return out


def read_single_registers(client, start, count, unit):
    """Read both Holding Registers (HR) and Input Registers (IR)."""
    out = _read_reg_table(client.read_holding_registers, "HR", start, count, unit)
    out.update(_read_reg_table(client.read_input_registers, "IR", start, count, unit))
    return out


def _format_dump_lines(regs, args, timestamp=None):
    header = (
        f"# Host: {args.host}:{args.port} unit={args.unit} "
        f"range={args.start}..{args.start + args.count - 1} base={args.base}"
    )
    if timestamp:
        header += f" time={timestamp}"
    lines = [
        header,
        f"{'reg':>9} | {'uint16':>6} | {'hex':>6} | binary",
        "-" * 49,
    ]
    for key in sorted(regs, key=lambda k: (k.split(":")[0], int(k.split(":")[1]))):
        val = regs[key]
        if not args.all and val == 0:
            continue
        prefix, raw_addr = key.split(":")
        reg_shown = f"{prefix}:{int(raw_addr) + args.base}"
        lines.append(f"{reg_shown:>9} | {val:>6} | 0x{val:04x} | {val:016b}")
    return lines


def dump_registers(client, args):
    if not args.loop:
        regs = read_single_registers(client, args.start, args.count, args.unit)
        lines = _format_dump_lines(regs, args)
        text = "\n".join(lines) + "\n"
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Wrote {len(lines) - 3} register(s) to {args.out}")
        else:
            print(text, end="")
        return

    out_f = open(args.out, "w", encoding="utf-8") if args.out else None
    try:
        prev = None
        cycle = 0
        print(f"Continuously dumping {args.host} every {args.delay}s (Ctrl+C to stop)...")
        while True:
            cycle += 1
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            regs = read_single_registers(client, args.start, args.count, args.unit)
            if prev is None:
                lines = _format_dump_lines(regs, args, timestamp=now_str)
                block = "\n".join(lines) + "\n\n"
                if out_f:
                    out_f.write(block)
                    out_f.flush()
                    print(f"[{now_str}] Initial dump: {len(lines) - 3} register(s) -> {args.out}")
                else:
                    print(block, end="", flush=True)
            else:
                all_keys = sorted(set(prev) | set(regs), key=lambda k: (k.split(":")[0], int(k.split(":")[1])))
                changed = []
                for key in all_keys:
                    va, vb = prev.get(key, 0), regs.get(key, 0)
                    if va != vb:
                        prefix, raw_addr = key.split(":")
                        changed.append((f"{prefix}:{int(raw_addr) + args.base}", va, vb))
                if changed:
                    lines = [f"# Changes at {now_str} (cycle {cycle}):"]
                    for reg_shown, va, vb in changed:
                        lines.append(
                            f"{reg_shown:>9} | {va:>6} (0x{va:04x}) -> {vb:>6} (0x{vb:04x} | {vb:016b})"
                        )
                    block = "\n".join(lines) + "\n\n"
                    if out_f:
                        out_f.write(block)
                        out_f.flush()
                    print(block, end="", flush=True)
                else:
                    print(f"[{now_str}] cycle {cycle}: no changes", flush=True)
            prev = regs
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if out_f:
            out_f.close()


def _parse_dump(path):
    regs = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("reg") or line.startswith("-"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                regs[int(parts[0])] = int(parts[1])
    return regs


def diff_dumps(path_a, path_b):
    a = _parse_dump(path_a)
    b = _parse_dump(path_b)
    all_regs = sorted(set(a) | set(b))
    changed = [(r, a.get(r, 0), b.get(r, 0)) for r in all_regs if a.get(r, 0) != b.get(r, 0)]
    if not changed:
        print("No differences found.")
        return
    print(f"{len(changed)} register(s) changed between {path_a} and {path_b}:\n")
    print(f"{'reg':>6} | {'before':>15} | {'after':>15}")
    print("-" * 44)
    for r, va, vb in changed:
        print(f"{r:>6} | {va:>6} (0x{va:04x}) | {vb:>6} (0x{vb:04x})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host", nargs="?")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=2000)
    ap.add_argument("--base", type=int, default=0, choices=[0, 1])
    ap.add_argument("--unit", type=int, default=1)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--dump", action="store_true",
                    help="dump non-zero 16-bit holding registers (use --all to include zeros)")
    ap.add_argument("--loop", action="store_true",
                    help="with --dump, poll continuously every --delay seconds and log changes until Ctrl+C")
    ap.add_argument("--all", action="store_true",
                    help="with --dump, include registers whose value is 0")
    ap.add_argument("--out", type=str, default=None,
                    help="write --dump output to a file")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE_FILE", "AFTER_FILE"),
                    help="compare two --dump output files")
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--delay", type=float, default=8.0,
                    help="seconds between reads (must cross display updates)")
    ap.add_argument("--max-gas", type=float, default=2000.0,
                    help="ignore values whose magnitude exceeds this")
    ap.add_argument("--display", type=float, nargs="*", default=None,
                    help="values currently on the screen, to highlight matches")
    args = ap.parse_args()

    if args.diff:
        diff_dumps(args.diff[0], args.diff[1])
        return

    if not args.host:
        ap.error("host is required unless using --diff")

    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient(args.host, port=args.port)
    if not client.connect():
        print(f"FAIL: could not connect to {args.host}:{args.port}")
        return
    try:
        if args.watch:
            watch(client, args)
        elif args.dump:
            dump_registers(client, args)
        else:
            print("Use --watch or --dump (optionally --out file.txt).")
    finally:
        client.close()


if __name__ == "__main__":
    main()
