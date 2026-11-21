import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import IntakeSource from "./IntakeSource";

const TEXT = "Công ty Sao Mai\nMã số thuế: 0101234567\nĐiện thoại: 0912345678";
const at = (needle, len = needle.length) => { const s = TEXT.indexOf(needle); return [s, s + len]; };

const FIELDS = {
  company_name: { value: "Công ty Sao Mai", source: { spans: [at("Công ty Sao Mai")], boxes: [{ page: 0, x: 0.1, y: 0.2, w: 0.3, h: 0.05 }] } },
  company_tax_code: { value: "0101234567", raw: "0I01234567", source: { spans: [at("0101234567")], boxes: [{ page: 0, x: 0.5, y: 0.4, w: 0.2, h: 0.04 }, { page: 1, x: 0.1, y: 0.1, w: 0.2, h: 0.04 }] } },
  mentor_phone: { value: "0912345678", source: { spans: [at("0912345678")] } },
  position: { value: "Backend" }, // không có vị trí → bỏ qua
};

const TEXT_DOC = { text: TEXT };
const IMAGE_DOC = {
  text: TEXT,
  pages: [{ index: 0, image: "data:image/png;base64,AAA", width: 800, height: 1000 }, { index: 1, image: "data:image/png;base64,BBB", width: 800, height: 1000 }],
};

const setup = (doc, props = {}) => {
  const onSelect = vi.fn();
  const utils = render(<IntakeSource document={doc} fields={FIELDS} active={null} onSelect={onSelect} {...props} />);
  return { onSelect, user: userEvent.setup(), ...utils };
};

describe("IntakeSource — file chỉ có văn bản", () => {
  it("không có tab; tô đúng đoạn của từng trường, bỏ qua trường không có vị trí", () => {
    const { container } = setup(TEXT_DOC);
    expect(screen.getByText("Nội dung file")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    const marks = [...container.querySelectorAll("mark")];
    expect(marks.map((m) => [m.dataset.field, m.textContent])).toEqual([
      ["company_name", "Công ty Sao Mai"], ["company_tax_code", "0101234567"], ["mentor_phone", "0912345678"],
    ]);
    expect(marks[1]).toHaveAttribute("title", "Mã số thuế");
  });

  it("giữ nguyên phần văn bản nằm ngoài các đoạn tô", () => {
    const { container } = setup(TEXT_DOC);
    expect(container.querySelector("pre").textContent).toBe(TEXT);
  });

  it("bấm đoạn tô → chọn trường; trường đang chọn có class is-active", async () => {
    const { user, onSelect, container } = setup(TEXT_DOC, { active: "company_tax_code" });
    expect(container.querySelector('mark[data-field="company_tax_code"]')).toHaveClass("is-active");
    expect(container.querySelector('mark[data-field="company_name"]')).not.toHaveClass("is-active");
    await user.click(container.querySelector('mark[data-field="mentor_phone"]'));
    expect(onSelect).toHaveBeenCalledWith("mentor_phone");
  });

  it("đoạn chồng lên đoạn trước thì bỏ qua, không lặp chữ", () => {
    const fields = {
      a: { value: "x", source: { spans: [[0, 15]] } },
      b: { value: "y", source: { spans: [[5, 10]] } }, // nằm trong a → bỏ
    };
    const { container } = render(<IntakeSource document={TEXT_DOC} fields={fields} active={null} onSelect={() => {}} />);
    expect(container.querySelectorAll("mark")).toHaveLength(1);
    expect(container.querySelector("pre").textContent).toBe(TEXT);
  });

  it("không trường nào có vị trí → hiện nguyên văn bản", () => {
    const { container } = render(<IntakeSource document={TEXT_DOC} fields={{ x: { value: "1" } }} active={null} onSelect={() => {}} />);
    expect(container.querySelectorAll("mark")).toHaveLength(0);
    expect(container.querySelector("pre").textContent).toBe(TEXT);
  });

  it("văn bản bị cắt → ghi chú chỉ hiển thị phần đầu; không cắt thì không ghi", () => {
    const { unmount } = setup({ ...TEXT_DOC, truncated: true });
    expect(screen.getByText(/Chỉ hiển thị phần đầu văn bản/)).toBeInTheDocument();
    unmount();
    setup(TEXT_DOC);
    expect(screen.queryByText(/Chỉ hiển thị phần đầu văn bản/)).not.toBeInTheDocument();
  });

  it("nhắc người dùng chữ có thể sai chữ số", () => {
    setup(TEXT_DOC);
    expect(screen.getByText(/nếu sai chữ số thì nên nhập tay/)).toBeInTheDocument();
  });
});

describe("IntakeSource — bản scan/ảnh", () => {
  it("mặc định xem bản gốc: ảnh từng trang kèm chú thích trang", () => {
    setup(IMAGE_DOC);
    expect(screen.getByText("File bạn đã tải lên")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Bản gốc" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByAltText("Trang 1 của file đã tải lên")).toHaveAttribute("src", "data:image/png;base64,AAA");
    expect(screen.getByAltText("Trang 2 của file đã tải lên")).toBeInTheDocument();
    expect(screen.getByText("Trang 1/2")).toBeInTheDocument();
  });

  it("khung nằm đúng vị trí (tỉ lệ %) và đúng trang", () => {
    setup(IMAGE_DOC);
    const box = screen.getByRole("button", { name: "Tên doanh nghiệp: Công ty Sao Mai" });
    expect(box).toHaveStyle({ left: "10%", top: "20%", width: "30%", height: "5%" });
    // MST có 2 khung ở 2 trang khác nhau; nhãn ưu tiên giá trị đọc thô (raw) để người dùng đối chiếu
    expect(screen.getAllByRole("button", { name: "Mã số thuế: 0I01234567" })).toHaveLength(2);
    const frames = document.querySelectorAll(".src-page__frame");
    expect(frames[0].querySelectorAll("button")).toHaveLength(2); // tên DN + MST ở trang 1
    expect(frames[1].querySelectorAll("button")).toHaveLength(1); // MST ở trang 2
  });

  it("trường không có khung (chỉ có đoạn văn bản) thì không có khung trên ảnh", () => {
    setup(IMAGE_DOC);
    expect(screen.queryByRole("button", { name: /SĐT người hướng dẫn/ })).not.toBeInTheDocument();
  });

  it("bấm khung → chọn trường", async () => {
    const { user, onSelect } = setup(IMAGE_DOC);
    await user.click(screen.getByRole("button", { name: /Tên doanh nghiệp/ }));
    expect(onSelect).toHaveBeenCalledWith("company_name");
  });

  it("trường đang chọn: mọi khung sáng; mỗi trang chỉ khung đầu có nhãn nổi và data-field (điểm cuộn tới)", () => {
    setup(IMAGE_DOC, { active: "company_tax_code" });
    const boxes = screen.getAllByRole("button", { name: /Mã số thuế/ });
    expect(boxes.every((b) => b.classList.contains("is-active"))).toBe(true);
    expect(boxes).toHaveLength(2); // một khung ở mỗi trang
    boxes.forEach((b) => expect(b).toHaveAttribute("data-field", "company_tax_code"));
    expect(document.querySelectorAll(".src-box__tag")).toHaveLength(2);
    // trang 1 có thêm khung "Tên doanh nghiệp" (không phải trường đang chọn): không có data-field/nhãn nổi ngoài khung đầu của nó
    expect(screen.getByRole("button", { name: /Tên doanh nghiệp/ }).querySelector(".src-box__tag")).toBeNull()
    expect(screen.getByRole("button", { name: /Tên doanh nghiệp/ })).not.toHaveClass("is-active");
  });

  it("chuyển sang 'Văn bản nhận dạng' rồi quay lại", async () => {
    const { user, container } = setup(IMAGE_DOC);
    await user.click(screen.getByRole("tab", { name: "Văn bản nhận dạng" }));
    expect(screen.getByRole("tab", { name: "Văn bản nhận dạng" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByAltText(/Trang 1/)).not.toBeInTheDocument();
    expect(container.querySelectorAll("mark")).toHaveLength(3);
    await user.click(screen.getByRole("tab", { name: "Bản gốc" }));
    expect(screen.getByAltText("Trang 1 của file đã tải lên")).toBeInTheDocument();
  });

  it("lời nhắc đổi theo tab", async () => {
    const { user } = setup(IMAGE_DOC);
    expect(screen.getByText(/Khung sáng là chỗ hệ thống đọc ra giá trị/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Văn bản nhận dạng" }));
    expect(screen.getByText(/Đoạn được tô là chỗ giá trị được lấy ra/)).toBeInTheDocument();
  });

  it("trường có source nhưng không có boxes không làm vỡ giao diện", () => {
    const fields = { a: { value: "x", source: { spans: [[0, 3]] } } };
    render(<IntakeSource document={IMAGE_DOC} fields={fields} active="a" onSelect={() => {}} />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
