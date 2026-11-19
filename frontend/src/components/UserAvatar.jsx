import { useEffect, useState } from "react";

export default function UserAvatar({ user, className = "", alt = "Ảnh đại diện" }) {
  const name = user?.username || user?.email || "?";
  const initial = String(name).charAt(0).toUpperCase();
  const avatarUrl = user?.avatar_url;
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    setImageFailed(false);
  }, [avatarUrl]);

  return (
    <span className={`user-avatar ${className}`.trim()} aria-label={alt}>
      {avatarUrl && !imageFailed ? (
        <img src={avatarUrl} alt={alt} onError={() => setImageFailed(true)} />
      ) : (
        initial
      )}
    </span>
  );
}