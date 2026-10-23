interface ErrorNoticeProps {
  title: string
  message: string
}

export function ErrorNotice({ title, message }: ErrorNoticeProps) {
  return (
    <div className="notice notice--error" role="alert">
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  )
}
