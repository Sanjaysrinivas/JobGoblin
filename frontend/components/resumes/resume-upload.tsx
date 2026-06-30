"use client";

import * as React from "react";
import { Loader2, Upload } from "lucide-react";

import { ApiError } from "@/lib/api";
import { uploadResume, type ResumeDetail } from "@/lib/resumes";
import { Button } from "@/components/ui/button";

const ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

interface ResumeUploadProps {
  /** Called with the created resume once the upload + parse succeeds. */
  onUploaded?: (resume: ResumeDetail) => void;
  variant?: React.ComponentProps<typeof Button>["variant"];
  label?: string;
}

/**
 * A button that opens a file picker and uploads the chosen PDF/DOCX. The backend
 * extracts text and parses sections inline, so the returned resume is ready to
 * render.
 */
export function ResumeUpload({
  onUploaded,
  variant = "default",
  label = "Upload resume",
}: ResumeUploadProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset the input so selecting the same file again re-triggers change.
    e.target.value = "";
    if (!file) return;

    setError(null);
    setPending(true);
    try {
      const resume = await uploadResume(file);
      onUploaded?.(resume);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Upload failed.");
      } else {
        setError("Could not reach the server. Is the backend running?");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={onChange}
        disabled={pending}
      />
      <Button
        type="button"
        variant={variant}
        disabled={pending}
        onClick={() => inputRef.current?.click()}
      >
        {pending ? (
          <>
            <Loader2 className="size-4 animate-spin" />
            Uploading…
          </>
        ) : (
          <>
            <Upload className="size-4" />
            {label}
          </>
        )}
      </Button>
      {error && (
        <p role="alert" className="text-destructive text-xs">
          {error}
        </p>
      )}
    </div>
  );
}
