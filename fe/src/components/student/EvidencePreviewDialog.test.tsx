import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FilePicker } from "@/components/ui/ui";
import EvidencePreviewDialog from "./EvidencePreviewDialog";

beforeAll(() => {
  // jsdom chưa có URL.createObjectURL.
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});

// Ghép giống trang Mốc: chọn tệp -> popup xem lại -> Tải lên / Hủy.
function Harness({ onUpload }: { onUpload: (file: File) => void }) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <>
      <FilePicker label="Tải minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" onFile={setFile} />
      <EvidencePreviewDialog
        file={file}
        busy={false}
        onCancel={() => setFile(null)}
        onConfirm={() => {
          if (file) onUpload(file);
          setFile(null);
        }}
      />
    </>
  );
}

function pickFile(container: HTMLElement, file: File) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  return userEvent.upload(input, file);
}

describe("EvidencePreviewDialog", () => {
  it("chọn tệp thì hiện popup xem lại, chưa tải lên cho tới khi bấm Tải lên", async () => {
    const onUpload = vi.fn();
    const { container } = render(<Harness onUpload={onUpload} />);
    expect(screen.queryByRole("dialog")).toBeNull();

    await pickFile(container, new File(["x"], "bao-cao.png", { type: "image/png" }));

    expect(await screen.findByRole("dialog", { name: "Xem lại minh chứng" })).toBeTruthy();
    expect(screen.getByText("bao-cao.png")).toBeTruthy();
    expect(onUpload).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Tải lên" }));
    expect(onUpload).toHaveBeenCalledTimes(1);
    expect((onUpload.mock.calls[0][0] as File).name).toBe("bao-cao.png");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Hủy thì đóng popup và không tải lên", async () => {
    const onUpload = vi.fn();
    const { container } = render(<Harness onUpload={onUpload} />);
    await pickFile(container, new File(["x"], "giay.pdf", { type: "application/pdf" }));
    await userEvent.click(await screen.findByRole("button", { name: "Hủy" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("tệp DOCX không xem trước được thì có lời nhắc", async () => {
    const { container } = render(<Harness onUpload={vi.fn()} />);
    await pickFile(container, new File(["x"], "bao-cao.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }));
    expect(await screen.findByText(/Không xem trước được/)).toBeTruthy();
  });
});
