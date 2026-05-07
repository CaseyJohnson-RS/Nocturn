import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Badge } from '@/components/ui/Badge';

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>#typescript</Badge>);
    expect(screen.getByText('#typescript')).toBeInTheDocument();
  });

  // Variant colour classes (from Badge.tsx variants map)
  it('uses default variant styles (bg-bg-selected) when no variant given', () => {
    render(<Badge>tag</Badge>);
    expect(screen.getByText('tag').closest('span')).toHaveClass('bg-bg-selected');
  });

  it('applies success variant', () => {
    render(<Badge variant="success">ok</Badge>);
    expect(screen.getByText('ok').closest('span')).toHaveClass('bg-success/15');
  });

  it('applies danger variant', () => {
    render(<Badge variant="danger">err</Badge>);
    expect(screen.getByText('err').closest('span')).toHaveClass('bg-danger/15');
  });

  it('applies warning variant', () => {
    render(<Badge variant="warning">warn</Badge>);
    expect(screen.getByText('warn').closest('span')).toHaveClass('bg-warning/15');
  });

  it('fires onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<Badge onClick={onClick}>click me</Badge>);
    await userEvent.click(screen.getByText('click me'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('adds cursor-pointer when onClick is provided', () => {
    render(<Badge onClick={() => {}}>clickable</Badge>);
    expect(screen.getByText('clickable').closest('span')).toHaveClass('cursor-pointer');
  });

  it('does not add cursor-pointer when onClick is absent', () => {
    render(<Badge>plain</Badge>);
    expect(screen.getByText('plain').closest('span')).not.toHaveClass('cursor-pointer');
  });
});
