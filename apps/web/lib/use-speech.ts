"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* Browser Web Speech API: Hindi/English voice input and read-aloud, no paid APIs.
   Chrome and Edge support recognition; Safari/Firefox fall back to typing. */

type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

export function useSpeech(lang: string) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const rec = useRef<Recognition | null>(null);

  useEffect(() => {
    const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) return;
    const r = new Ctor();
    r.lang = lang;
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => setTranscript(e.results[0]?.[0]?.transcript ?? "");
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setSupported(true);
  }, [lang]);

  const listen = useCallback(() => {
    if (!rec.current) return;
    setTranscript("");
    setListening(true);
    rec.current.start();
  }, []);
  const stop = useCallback(() => rec.current?.stop(), []);
  const reset = useCallback(() => setTranscript(""), []);
  const say = useCallback(
    (text: string) => {
      if (!("speechSynthesis" in window)) return;
      const u = new SpeechSynthesisUtterance(text.replace(/•/g, ""));
      u.lang = lang;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    },
    [lang],
  );

  return useMemo(
    () => ({ supported, listening, transcript, listen, stop, reset, say }),
    [supported, listening, transcript, listen, stop, reset, say],
  );
}
