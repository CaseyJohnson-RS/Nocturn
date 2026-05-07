import { type InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ error, label, id, className = '', ...rest }, ref) => (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-[11px] text-fg-muted font-medium uppercase tracking-wide">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={`w-full bg-bg-input border rounded px-3 py-2 text-[13px] text-fg outline-none placeholder:text-fg-muted transition-colors
          ${error ? 'border-danger focus:border-danger' : 'border-border focus:border-border-focus'}
          ${className}`}
        {...rest}
      />
      {error && <span className="text-[11px] text-danger">{error}</span>}
    </div>
  ),
);
Input.displayName = 'Input';
