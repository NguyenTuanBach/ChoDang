import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// jsdom chưa cài các hàm cuộn mà giao diện gọi khi chọn một trường để xem nguồn
Element.prototype.scrollTo ??= () => {};
Element.prototype.scrollIntoView ??= () => {};
