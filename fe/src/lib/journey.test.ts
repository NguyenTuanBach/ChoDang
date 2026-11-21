import { describe, expect, it } from "vitest";
import { journey } from "./journey";

const states = (status: string | null) => journey(status).map((s) => s.state);

describe("journey", () => {
  it("chưa có hồ sơ: đang ở bước Hồ sơ", () => {
    expect(states(null)).toEqual(["current", "todo", "todo", "todo", "todo"]);
  });

  it("đã xác nhận: Hồ sơ xong, đang ở Đề cương", () => {
    expect(states("confirmed")).toEqual(["done", "current", "todo", "todo", "todo"]);
  });

  it("đang thực tập: Hồ sơ và Đề cương xong, đang ở Thực tập", () => {
    expect(states("in_progress")).toEqual(["done", "done", "current", "todo", "todo"]);
  });

  it("chờ thẩm định tín chỉ: đã qua Kết thúc, đang ở Tín chỉ", () => {
    expect(states("pending_credit")).toEqual(["done", "done", "done", "done", "current"]);
  });

  it("hoàn thành: tất cả xong", () => {
    expect(states("completed")).toEqual(["done", "done", "done", "done", "done"]);
  });

  it("hồ sơ bị từ chối hoặc không công nhận: bước đó báo lỗi", () => {
    expect(states("rejected")[0]).toBe("failed");
    expect(states("closed_no_credit")[4]).toBe("failed");
  });

  it("trạng thái lạ: coi như bước đầu, không lỗi", () => {
    expect(states("khong-biet")).toEqual(["current", "todo", "todo", "todo", "todo"]);
  });
});
