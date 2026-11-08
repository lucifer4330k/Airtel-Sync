"use client";

import { FileText, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { CheckList, ResultIcon } from "@/components/kyc/check-list";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiError, type DocType, type KycCase, type KycDocument } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,application/pdf";

export function DocumentRow({
  kycCase,
  docType,
  doc,
  onUploaded,
}: {
  kycCase: KycCase;
  docType: DocType;
  doc?: KycDocument;
  onUploaded: () => void;
}) {
  const t = useTranslations("kyc");
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = `file-${docType}`;

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    // Quick client-side checks; the server re-checks the actual bytes.
    if (file.size > MAX_BYTES) return setError(t("too_big"));
    if (!ACCEPT.split(",").includes(file.type)) return setError(t("wrong_type"));
    setBusy(true);
    try {
      await api.uploadDocument(kycCase, docType, file);
      onUploaded();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error", { message: String(e) }));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <li className="rounded-bill border border-line bg-surface p-3">
      <div className="flex items-center gap-3">
        {doc ? (
          <ResultIcon result={doc.result} className="size-5" />
        ) : (
          <FileText aria-hidden className="size-5 shrink-0 text-ink-soft" />
        )}
        <div className="min-w-0 flex-1">
          <p className="font-medium">{t(`docs.${docType}`)}</p>
          <p className="text-sm text-ink-soft">
            {doc ? `${t(`result.${doc.result}`)} · ${doc.file.file_type}, ${doc.file.size}` : t("not_uploaded")}
          </p>
        </div>
        <input
          ref={input}
          id={inputId}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          disabled={busy}
          onChange={(e) => onFile(e.target.files?.[0])}
        />
        <label
          htmlFor={inputId}
          className={cn(
            buttonVariants({ variant: "quiet" }),
            "min-h-11 px-4 text-sm",
            busy && "pointer-events-none opacity-60",
          )}
        >
          {busy ? (
            <>
              <Loader2 aria-hidden className="size-4 animate-spin" />
              {t("uploading")}
            </>
          ) : doc ? (
            t("replace")
          ) : (
            t("upload")
          )}
        </label>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-alert">
          {error}
        </p>
      )}
      {doc && <CheckList checks={doc.checks} />}
    </li>
  );
}
