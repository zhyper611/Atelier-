type AuthAlertProps = {
  message: string;
};

export function AuthAlert({ message }: AuthAlertProps) {
  return (
    <div className="auth-alert" role="alert" aria-live="polite">
      <span className="auth-alert__icon" aria-hidden="true">
        !
      </span>
      <p className="auth-alert__text">{message}</p>
    </div>
  );
}
