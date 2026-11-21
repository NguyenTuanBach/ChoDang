// Liên kết tải tệp qua endpoint kiểm quyền của BE (cùng origin, cookie phiên tự đính kèm).
export default function DownloadDoc({ href, name }: { href: string; name: string }) {
  return (
    <a href={href} download>
      {name}
    </a>
  );
}
