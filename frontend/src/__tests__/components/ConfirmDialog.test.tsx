import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

const defaults = {
  title: 'Delete note',
  message: 'This cannot be undone.',
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ConfirmDialog', () => {
  it('renders title and message', () => {
    render(<ConfirmDialog {...defaults} />);
    expect(screen.getByText('Delete note')).toBeInTheDocument();
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument();
  });

  it('shows custom confirmLabel', () => {
    render(<ConfirmDialog {...defaults} confirmLabel="Yes, delete" />);
    expect(screen.getByRole('button', { name: 'Yes, delete' })).toBeInTheDocument();
  });

  it('shows custom cancelLabel', () => {
    render(<ConfirmDialog {...defaults} cancelLabel="Never mind" />);
    expect(screen.getByRole('button', { name: 'Never mind' })).toBeInTheDocument();
  });

  it('calls onConfirm when the confirm button is clicked', async () => {
    render(<ConfirmDialog {...defaults} confirmLabel="Confirm" />);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(defaults.onConfirm).toHaveBeenCalledOnce();
  });

  it('calls onCancel when the cancel button is clicked', async () => {
    render(<ConfirmDialog {...defaults} cancelLabel="Cancel" />);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(defaults.onCancel).toHaveBeenCalledOnce();
  });

  it('uses danger variant on confirm button when danger=true', () => {
    render(<ConfirmDialog {...defaults} confirmLabel="Delete" danger />);
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveClass('bg-danger');
  });

  it('uses primary variant on confirm button when danger=false', () => {
    render(<ConfirmDialog {...defaults} confirmLabel="OK" />);
    expect(screen.getByRole('button', { name: 'OK' })).toHaveClass('bg-accent');
  });

  it('disables cancel and shows spinner on confirm button while loading', () => {
    render(
      <ConfirmDialog {...defaults} confirmLabel="Save" cancelLabel="Back" loading />,
    );
    // When loading, the confirm button replaces its text with an aria-hidden spinner,
    // so its accessible name becomes "". Query all buttons and check both are disabled.
    const [cancelBtn, confirmBtn] = screen.getAllByRole('button');
    expect(cancelBtn).toBeDisabled();  // "Back"
    expect(confirmBtn).toBeDisabled(); // spinner (no accessible name while loading)
  });
});
