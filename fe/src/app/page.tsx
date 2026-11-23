import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import LandingCta from "@/components/shared/LandingCta";

export const metadata: Metadata = {
  title: "VIN-15 | Người đồng hành cho kỳ thực tập của bạn",
};

const TAGS = ["Hỏi đáp quy chế có trích dẫn", "Theo dõi tiến độ", "Thẩm định bởi giảng viên", "Quy đổi tín chỉ"];

const STEPS = [
  { title: "Nộp hồ sơ thực tập", text: "Điền thông tin doanh nghiệp và vị trí; AI gợi ý chuẩn hóa các trường để bạn khỏi nhập sai." },
  { title: "Hoàn thiện đề cương", text: "Soạn đề cương, giảng viên xem và phê duyệt trước khi bạn bắt đầu." },
  { title: "Báo cáo theo mốc", text: "Cập nhật nhật ký và minh chứng theo từng mốc; hệ thống nhắc khi sắp trễ hạn." },
  { title: "Thẩm định và công nhận", text: "Giảng viên thẩm định, quản trị viên phê duyệt tín chỉ và đồng bộ sang hệ thống đào tạo." },
];

const FEATURES: { eyebrow: string; title: string; text: string; rows?: string[]; image?: { src: string; alt: string; width: number; height: number } }[] = [
  {
    eyebrow: "Trợ lý chính sách",
    title: "Hỏi quy chế, nhận câu trả lời có điều khoản.",
    text: "Trợ lý trả lời theo văn bản quy định hiện hành và luôn trích dẫn nguồn. Câu hỏi về hồ sơ của riêng bạn cũng được trả lời từ dữ liệu thật.",
    image: { src: "/landing/assistant.png", alt: "Giao diện Trợ lý thực tập", width: 1607, height: 864 },
  },
  {
    eyebrow: "Theo dõi tiến độ",
    title: "Mọi mốc và minh chứng, một nơi.",
    text: "Thanh hành trình cho biết bạn đang ở bước nào, việc gì cần làm tiếp và hạn nộp. Giảng viên thấy cảnh báo sớm khi sinh viên chậm tiến độ.",
    image: { src: "/landing/progress-tracker.png", alt: "Trang Mốc và minh chứng của sinh viên với các mốc đã chấp nhận, mốc hiện tại và mốc chờ nộp", width: 1888, height: 868 },
  },
  {
    eyebrow: "Phê duyệt",
    title: "Hàng chờ gọn cho giảng viên và quản trị viên.",
    text: "Đề cương, ngoại lệ và quy đổi tín chỉ đi qua hàng chờ phê duyệt, kèm gợi ý tiền thẩm của AI để người duyệt xem nhanh hơn.",
    rows: ["Đề cương · chờ duyệt", "Gia hạn 2 tuần · chờ duyệt", "Quy đổi 6 tín chỉ · chờ duyệt"],
  },
];

const CONTROL = [
  { lead: "Mọi quyết định do con người.", text: "Phê duyệt đề cương, xử lý ngoại lệ và công nhận tín chỉ luôn cần giảng viên hoặc quản trị viên xác nhận." },
  { lead: "AI không ghi vào hệ thống đào tạo.", text: "Chỉ kết quả đã được quản trị viên phê duyệt mới được đồng bộ." },
  { lead: "Thông tin cá nhân được che.", text: "Dữ liệu sinh viên và doanh nghiệp được che trước khi gửi tới mô hình ngoài." },
];

const POSTS = [
  { tag: "Hướng dẫn", date: "20/11/2026", title: "Chuẩn bị hồ sơ thực tập: cần những gì?", text: "Danh sách giấy tờ, thông tin doanh nghiệp và lưu ý để hồ sơ được xác nhận ngay lần đầu." },
  { tag: "Quy chế", date: "18/11/2026", title: "Cách tính và quy đổi tín chỉ thực tập", text: "Điều kiện công nhận, vai trò của giảng viên thẩm định và bước phê duyệt của quản trị viên." },
  { tag: "Mẹo", date: "15/11/2026", title: "Viết nhật ký tuần và nộp minh chứng đúng hạn", text: "Gợi ý ghi nhật ký ngắn gọn, chọn minh chứng phù hợp và tránh bị nhắc trễ hạn." },
];

const FAQ = [
  { q: "Trợ lý có tự quyết định thay giảng viên không?", a: "Không. Trợ lý chỉ giải đáp và gợi ý. Mọi bước phê duyệt đều do người thực hiện." },
  { q: "Câu trả lời về quy chế lấy từ đâu?", a: "Từ kho quy định đã được quản trị viên xuất bản, kèm trích dẫn điều khoản để bạn tự đối chiếu." },
  { q: "Thông tin của tôi có bị gửi cho bên thứ ba không?", a: "Thông tin định danh được che trước khi gửi tới mô hình ngôn ngữ; khóa truy cập mô hình chỉ nằm ở dịch vụ AI, không ở trình duyệt." },
  { q: "Ai dùng được hệ thống?", a: "Sinh viên, giảng viên và quản trị viên, mỗi vai trò có giao diện và phạm vi quyền riêng." },
  { q: "Tín chỉ được ghi vào hệ thống đào tạo như thế nào?", a: "Sau khi quản trị viên phê duyệt, một tác vụ đồng bộ được tạo và ghi vào hệ thống đào tạo của trường." },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-background focus:px-3 focus:py-1">
        Chuyển tới nội dung
      </a>
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link href="/" className="text-lg font-semibold tracking-tight">VIN-15</Link>
          <nav className="flex items-center gap-5 text-sm">
            <a href="#how" className="hidden text-muted-foreground hover:text-foreground sm:inline">Cách hoạt động</a>
            <a href="#posts" className="hidden text-muted-foreground hover:text-foreground sm:inline">Bài viết</a>
            <a href="#faq" className="hidden text-muted-foreground hover:text-foreground sm:inline">Hỏi đáp</a>
            <LandingCta size="default" />
          </nav>
        </div>
      </header>

      <main id="main">
        <section className="mx-auto max-w-6xl px-6 pb-12 pt-16 text-center sm:pt-24">
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
            Người đồng hành cho kỳ thực tập của bạn.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground">
            Trợ lý AI giải đáp quy chế, nhắc tiến độ và một nơi duy nhất để quản lý hồ sơ, đề cương, mốc báo cáo đến công nhận tín chỉ.
          </p>
          <div className="mx-auto mt-14 max-w-4xl rounded-2xl border-2 border-foreground/25 bg-card p-3 shadow-sm">
            <div className="flex items-center gap-1.5 px-2 pb-3">
              <span className="size-2.5 rounded-full bg-muted-foreground/30" />
              <span className="size-2.5 rounded-full bg-muted-foreground/30" />
              <span className="size-2.5 rounded-full bg-muted-foreground/30" />
              <span className="ml-3 text-xs text-muted-foreground">VIN-15 · Trợ lý</span>
            </div>
            <div className="grid gap-3 rounded-xl bg-muted/50 p-4 text-left text-sm sm:grid-cols-[1fr_2fr]">
              <div className="space-y-2">
                {["Tổng quan", "Hồ sơ", "Đề cương", "Mốc & nhật ký", "Thẩm định"].map((item, i) => (
                  <div key={item} className={i === 0 ? "rounded-md bg-background px-3 py-2 font-medium" : "px-3 py-2 text-muted-foreground"}>{item}</div>
                ))}
              </div>
              <div className="space-y-3">
                <div className="ml-auto max-w-[80%] rounded-xl bg-primary px-3 py-2 text-primary-foreground">Em cần nộp gì để xin gia hạn thực tập?</div>
                <div className="max-w-[90%] rounded-xl bg-background px-3 py-2">
                  Bạn cần nộp đơn gia hạn kèm xác nhận của doanh nghiệp. Giảng viên sẽ xem và phê duyệt. <span className="text-muted-foreground">[Quy chế thực tập, Điều 12]</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="border-y-2 border-foreground/15 bg-background">
          <ul className="mx-auto m-0 grid max-w-6xl list-none grid-cols-2 p-0 md:grid-cols-4 md:divide-x md:divide-foreground/15">
            {TAGS.map((t) => (
              <li key={t} className="px-4 py-5 text-center text-sm font-medium">
                {t}
              </li>
            ))}
          </ul>
        </div>

        <section id="how" className="mx-auto max-w-6xl scroll-mt-16 px-6 py-16">
          <p className="text-sm font-medium text-primary">Từ đăng ký đến tín chỉ</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Một kỳ thực tập, bốn bước rõ ràng.</h2>
          <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="rounded-xl border-2 border-beige-strong bg-background p-5">
                <span className="flex size-8 items-center justify-center rounded-full border-2 border-beige-strong bg-beige text-sm font-semibold text-foreground">{i + 1}</span>
                <h3 className="mt-3 font-semibold">{s.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {FEATURES.map(({ eyebrow, title, text, rows, image }, i) => (
          <section key={eyebrow} className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-14 md:grid-cols-2">
            <div className={i % 2 === 1 ? "md:order-2" : ""}>
              <p className="text-sm font-medium text-primary">{eyebrow}</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight">{title}</h2>
              <p className="mt-4 text-muted-foreground">{text}</p>
            </div>
            {image ? (
              <div className="overflow-hidden rounded-2xl border-2 border-foreground/25 shadow-sm">
                <Image src={image.src} alt={image.alt} width={image.width} height={image.height} className="h-auto w-full" />
              </div>
            ) : (
              <div className="rounded-2xl border-2 border-foreground/25 bg-card p-4 shadow-sm">
                <div className="space-y-2">
                  {(rows ?? []).map((r) => (
                    <div key={r} className="rounded-lg border border-foreground/15 bg-background px-3 py-2 text-sm">{r}</div>
                  ))}
                </div>
              </div>
            )}
          </section>
        ))}

        <section className="mx-auto max-w-6xl px-6 py-16">
          <p className="text-sm font-medium text-primary">Bạn vẫn kiểm soát</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Tự động hóa có ranh giới phê duyệt rõ ràng.</h2>
          <ul className="mt-8 grid gap-4 md:grid-cols-3">
            {CONTROL.map((c) => (
              <li key={c.lead} className="rounded-xl bg-muted/50 p-5">
                <p className="font-semibold">{c.lead}</p>
                <p className="mt-1 text-sm text-muted-foreground">{c.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="posts" className="mx-auto max-w-6xl scroll-mt-16 px-6 py-16">
          <p className="text-sm font-medium text-primary">Bài viết</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Hướng dẫn và thông báo mới.</h2>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {POSTS.map((post) => (
              <article key={post.title} className="flex flex-col rounded-xl border-2 border-foreground/25 bg-card p-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="rounded-full border border-foreground/15 bg-background px-2.5 py-0.5 font-medium text-foreground">{post.tag}</span>
                  <time>{post.date}</time>
                </div>
                <h3 className="mt-4 font-semibold">{post.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{post.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="faq" className="mx-auto max-w-3xl scroll-mt-16 px-6 py-16">
          <h2 className="text-3xl font-bold tracking-tight">Câu hỏi thường gặp.</h2>
          <div className="mt-6 divide-y-2 divide-foreground/25 rounded-xl border-2 border-foreground/25 bg-card">
            {FAQ.map((f) => (
              <details key={f.q} className="group p-4">
                <summary className="cursor-pointer list-none font-medium marker:hidden">{f.q}</summary>
                <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-6 py-6 text-sm text-muted-foreground sm:flex-row">
          <span className="font-semibold text-foreground">VIN-15</span>
          <span>vin15 · người đồng hành cho kỳ thực tập của bạn</span>
        </div>
      </footer>
    </div>
  );
}
