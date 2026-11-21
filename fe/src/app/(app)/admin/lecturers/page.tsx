import AccountsPanel from "@/components/staff/AccountsPanel";

export default function Page() {
  return (
    <>
      <AccountsPanel viewer="admin" role="lecturer" title="Giảng viên" />
      <AccountsPanel viewer="admin" role="student" title="Sinh viên" />
    </>
  );
}
