import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders its children', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>No</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled while loading and shows a spinner', () => {
    render(<Button loading>Save</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    // spinner replaces text – children should not be visible
    expect(btn).not.toHaveTextContent('Save');
  });

  it('does not fire onClick while loading', async () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  // Variant class checks
  it('uses primary styles by default', () => {
    render(<Button>OK</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-accent');
  });

  it('uses danger styles for variant="danger"', () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-danger');
  });

  it('uses ghost styles for variant="ghost"', () => {
    render(<Button variant="ghost">Cancel</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-transparent');
  });

  // Size class checks  (sm: text-[11px] px-3 py-1 | md: text-[13px] px-4 py-2)
  it('applies sm size classes', () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveClass('px-3', 'py-1', 'text-[11px]');
  });

  it('applies md size classes by default', () => {
    render(<Button>Medium</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveClass('px-4', 'py-2', 'text-[13px]');
  });

  it('passes extra props through to the button element', () => {
    render(<Button type="submit" data-testid="submit-btn">Go</Button>);
    expect(screen.getByTestId('submit-btn')).toHaveAttribute('type', 'submit');
  });
});
