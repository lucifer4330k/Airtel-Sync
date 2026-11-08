"use client";

import { Check, CheckCheck, Mic } from "lucide-react";
import { type CSSProperties, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import s from "./landing.module.css";

/*
 * The owner's whole journey, pulled out of the phone in depth order:
 * chat on the screen, then the registry check, the plan, the checked document
 * and the WhatsApp update floating in front. Prices are the real Recommended
 * plan for an 8-person clinic in Pune (rules engine output).
 */

const PHONE_CENTER = { x: 278, y: 300 };

type Frag = { x: number; y: number; w: number; z: number; r?: number; delay: number };

function fragStyle({ x, y, w, z, r = 0, delay }: Frag): CSSProperties {
  return {
    "--x": `${x}px`,
    "--y": `${y}px`,
    "--w": `${w}px`,
    "--z": `${z}px`,
    "--r": `${r}deg`,
    "--delay": `${delay}ms`,
    // start inside the phone, so the fragments look pulled out of it
    "--fx": `${PHONE_CENTER.x - (x + w / 2)}px`,
    "--fy": `${PHONE_CENTER.y - (y + 60)}px`,
  } as CSSProperties;
}

const PLAN = [
  ["Biz Fibre 300", "1,629"],
  ["Business Postpaid × 3", "2,037"],
  ["Cloud Email × 5", "645"],
  ["Cloud Backup 1 TB", "579"],
  ["Endpoint Security × 4", "476"],
] as const;

export function ExplodedPhone() {
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setOpen(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      const box = el.getBoundingClientRect();
      const px = Math.max(-1, Math.min(1, ((e.clientX - box.left) / box.width) * 2 - 1));
      const py = Math.max(-1, Math.min(1, ((e.clientY - box.top) / box.height) * 2 - 1));
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--px", px.toFixed(3));
        el.style.setProperty("--py", py.toFixed(3));
      });
    };
    const reset = () => {
      el.style.setProperty("--px", "0");
      el.style.setProperty("--py", "0");
    };
    const host = el.closest("section") ?? el;
    host.addEventListener("pointermove", move as EventListener);
    host.addEventListener("pointerleave", reset);
    return () => {
      cancelAnimationFrame(frame);
      host.removeEventListener("pointermove", move as EventListener);
      host.removeEventListener("pointerleave", reset);
    };
  }, []);

  return (
    <div
      className={s.sceneWrap}
      role="img"
      aria-label="The owner app on a phone: a Hinglish chat with the advisor, the registry check, a ₹5,366 a month plan, a verified GST certificate and a WhatsApp update that the engineer visit is booked."
    >
      <div ref={ref} className={cn(s.scene, open && s.open)} aria-hidden>
        <div className={s.rig}>
          <div className={s.floor} />

          {/* the phone: advisor chat */}
          <div className={s.phone}>
            <div className={s.screen}>
              <div className="flex items-center justify-between border-b border-[rgb(222_226_233)] bg-white px-4 pb-2.5 pt-5">
                <span className="text-[13px] font-semibold">Advisor</span>
                <span className="rounded-full bg-[rgb(42_58_143/0.1)] px-2 py-0.5 text-[10px] font-medium text-[rgb(42_58_143)]">
                  हिं / EN
                </span>
              </div>
              <div className="flex flex-col gap-2.5 px-3 py-3 text-[11.5px] leading-snug">
                <p className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
                  What kind of business do you run?
                </p>
                <p className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-[rgb(42_58_143)] px-3 py-2 text-white">
                  Hum ek dental clinic chalate hain Pune mein, 8 log hain, internet bahut jata hai
                </p>
                <p className="max-w-[88%] rounded-2xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
                  One clinic, 8 people, and the internet drops. A backup line keeps billing running. What&apos;s your GSTIN?
                </p>
                <p className="ml-auto max-w-[70%] rounded-2xl rounded-tr-sm bg-[rgb(42_58_143)] px-3 py-2 font-mono text-[10.5px] text-white">
                  27XU•••••••1ZP
                </p>
                <p className="max-w-[88%] rounded-2xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
                  Found it. Here&apos;s the plan I&apos;d pick, with one monthly price.
                </p>
              </div>
              <div className="absolute inset-x-3 bottom-4 flex items-center justify-between rounded-full border border-[rgb(222_226_233)] bg-white px-4 py-2 text-[11px] text-[rgb(84_95_112)]">
                Type or speak…
                <Mic className="size-3.5 text-[rgb(42_58_143)]" />
              </div>
            </div>
          </div>

          {/* registry check */}
          <div className={s.frag} style={fragStyle({ x: 6, y: 92, w: 196, z: 190, delay: 150 })}>
            <div className="flex items-start gap-2 rounded-xl bg-white p-3 text-[rgb(28_37_51)] shadow-[0_18px_40px_-16px_rgb(0_0_0/0.5)]">
              <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-[rgb(30_122_76)] text-white">
                <Check className="size-3" strokeWidth={3} />
              </span>
              <span className="text-[11.5px] leading-snug">
                <span className="block font-semibold">GSTIN active</span>
                <span className="text-[rgb(84_95_112)]">Matched in the GST registry, details filled in</span>
              </span>
            </div>
          </div>

          {/* the plan */}
          <div className={s.frag} style={fragStyle({ x: 326, y: 118, w: 230, z: 130, delay: 300 })}>
            <div className="rounded-xl bg-white p-4 text-[rgb(28_37_51)] shadow-[0_24px_50px_-18px_rgb(0_0_0/0.55)]">
              <p className="flex items-center gap-1.5 text-[11px] font-medium text-[rgb(176_120_8)]">
                <span className="size-1.5 rounded-full bg-[rgb(227_162_26)]" /> Recommended
              </p>
              <p className="mt-1 font-display text-[28px] font-bold leading-none tracking-tight">
                ₹5,366<span className="ml-1 font-sans text-[12px] font-normal text-[rgb(84_95_112)]">a month, all-in</span>
              </p>
              <ul className="mt-3 flex flex-col gap-1 border-t border-dashed border-[rgb(222_226_233)] pt-2.5 text-[11px]">
                {PLAN.map(([name, price]) => (
                  <li key={name} className="flex justify-between gap-2">
                    <span className="text-[rgb(84_95_112)]">{name}</span>
                    <span className="money">₹{price}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2.5 text-[11px] text-[rgb(84_95_112)]">Installed in about 5 days</p>
            </div>
          </div>

          {/* checked document */}
          <div className={s.frag} style={fragStyle({ x: 0, y: 318, w: 190, z: 80, r: -5, delay: 450 })}>
            <div className="relative rounded-md bg-[rgb(253_252_248)] p-3.5 text-[rgb(28_37_51)] shadow-[0_20px_40px_-16px_rgb(0_0_0/0.5)]">
              <p className="text-[11px] font-semibold">Certificate of Registration</p>
              <p className="text-[9.5px] text-[rgb(84_95_112)]">Form GST REG-06</p>
              <div className="mt-2.5 flex flex-col gap-1.5">
                {[92, 70, 84, 56, 76].map((w, i) => (
                  <span key={i} className="h-1.5 rounded-full bg-[rgb(222_226_233)]" style={{ width: `${w}%` }} />
                ))}
              </div>
              <div className={s.stamp}>
                Verified
              </div>
            </div>
          </div>

          {/* WhatsApp update */}
          <div className={s.frag} style={fragStyle({ x: 334, y: 408, w: 214, z: 220, delay: 600 })}>
            <div className="rounded-xl rounded-tr-sm bg-[rgb(217_253_211)] p-3 text-[11.5px] leading-snug text-[rgb(17_27_33)] shadow-[0_22px_44px_-16px_rgb(0_0_0/0.55)]">
              <p className="font-semibold">Udyam Digital</p>
              <p className="mt-0.5">Documents verified. Engineer visit booked for Thursday, 10 am to 12 pm.</p>
              <p className="mt-1 flex items-center justify-end gap-1 text-[10px] text-[rgb(102_119_129)]">
                10:42 <CheckCheck className="size-3.5 text-[rgb(83_189_235)]" />
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
