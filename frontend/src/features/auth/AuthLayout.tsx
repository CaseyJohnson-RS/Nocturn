interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="h-full flex items-center justify-center bg-bg-base">
      <div className="flex flex-col gap-6 w-full max-w-[360px] px-4">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center font-bold text-xl text-white">
            N
          </div>
          <div className="text-center">
            <h1 className="text-[18px] font-semibold text-fg">{title}</h1>
            {subtitle && (
              <p className="text-[13px] text-fg-muted mt-1">{subtitle}</p>
            )}
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
