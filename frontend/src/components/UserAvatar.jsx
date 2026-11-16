export default function UserAvatar({ user, className = "", alt = "Ảnh đại diện" }) {
  const name = user?.username || user?.email || "?";
  const initial = String(name).charAt(0).toUpperCase();
  const avatarUrl = user?.avatar_url;

  return (
    <span className={`user-avatar ${className}`.trim()} aria-label={alt}>
      {avatarUrl ? <img src={avatarUrl} alt={alt} /> : initial}
    </span>
  );
}