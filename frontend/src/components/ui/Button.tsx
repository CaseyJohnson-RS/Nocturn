import { type ButtonHTMLAttributes, forwardRef } from 'react';

type Variant = 'primary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const base =
  'inline-flex items-center justify-center gap-1.5 font-medium cursor-pointer rounded disabled:opacity-40 disabled:cursor-not-allowed transition-opacity font-sans';

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-white hover:opacity-90',
  ghost: 'bg-transparent text-fg border border-border hover:bg-bg-hover',
  danger: 'bg-danger text-white hover:opacity-90',
};

const sizes: Record<Size, string> = {
  sm: 'text-[12px] px-4 py-1.5',
  md: 'text-[13px] px-5 py-2.5',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      disabled={disabled ?? loading}
      className={`${base} ${variants[variant]} ${sizes[size]}`}
      {...rest}
    >
      {loading ? <Spinner /> : children}
    </button>
  ),
);
Button.displayName = 'Button';

function Spinner() {
  return (
    <span
      className="inline-block w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin"
      aria-hidden
    />
  );
}
