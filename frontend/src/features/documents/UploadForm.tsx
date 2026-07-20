import { type FormEvent, useState } from "react";

import { ErrorState } from "../../components/feedback/ErrorState";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { useDocumentUpload } from "./hooks";
import { validatePdfFile } from "./validation";

export function UploadForm() {
  const upload = useDocumentUpload();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  function handleFileChange(files: FileList | null) {
    const file = files?.[0] ?? null;
    setSelectedFile(file);
    setValidationMessage(validatePdfFile(file));
    upload.reset();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validatePdfFile(selectedFile);
    setValidationMessage(validation);
    if (validation || !selectedFile) {
      return;
    }

    await upload.mutateAsync(selectedFile).catch(() => undefined);
  }

  return (
    <div className="stack">
      <Card>
        <form className="form-grid" onSubmit={handleSubmit}>
          <Input
            accept=".pdf,application/pdf"
            disabled={upload.isPending}
            error={validationMessage ?? undefined}
            helpText="One PDF, 10 MB maximum."
            label="PDF file"
            onChange={(event) => handleFileChange(event.currentTarget.files)}
            type="file"
          />
          {upload.isPending ? (
            <div aria-label="Upload progress" className="upload-progress" role="progressbar">
              <span style={{ width: `${upload.progress}%` }} />
            </div>
          ) : null}
          <Button disabled={upload.isPending || !selectedFile || validationMessage !== null} type="submit">
            {upload.isPending ? "Uploading" : "Upload PDF"}
          </Button>
        </form>
      </Card>
      {upload.isSuccess && upload.data ? (
        <Card>
          <h2>Upload accepted</h2>
          <p className="muted">
            {upload.data.filename} was accepted by the upload boundary with status {upload.data.status}.
          </p>
        </Card>
      ) : null}
      {upload.errorMessage ? (
        <ErrorState message={upload.errorMessage} title="Upload failed" />
      ) : null}
    </div>
  );
}

