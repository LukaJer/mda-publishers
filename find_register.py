

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


def read_block(client, start, count, unit):
    out = {}
    addr = start
    end = start + count
    while addr < end:
        try:
            rr = client.read_holding_registers(address=addr, count=2, slave=unit)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=2000)
    ap.add_argument("--base", type=int, default=0, choices=[0, 1])
    ap.add_argument("--unit", type=int, default=1)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--delay", type=float, default=8.0,
                    help="seconds between reads (must cross display updates)")
    ap.add_argument("--max-gas", type=float, default=2000.0,
                    help="ignore values whose magnitude exceeds this")
    ap.add_argument("--display", type=float, nargs="*", default=None,
                    help="values currently on the screen, to highlight matches")
    args = ap.parse_args()

    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient(args.host, port=args.port)
    if not client.connect():
        print(f"FAIL: could not connect to {args.host}:{args.port}")
        return
    try:
        if args.watch:
            watch(client, args)
        else:
            print("Use --watch  (optionally --display 0.01 2.53 2.61 to mark matches).")
    finally:
        client.close()


if __name__ == "__main__":
    main()
