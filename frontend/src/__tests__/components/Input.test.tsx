import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/ui/Input';

describe('Input', () => {
  it('renders a text input', () => {
    render(<Input id="name" />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders a label linked to the input', () => {
    render(<Input id="email" label="Email" />);
    // getByLabelText finds the input via the for/id association
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('does not render a label element when label prop is omitted', () => {
    render(<Input id="bare" />);
    expect(screen.queryByRole('label')).not.toBeInTheDocument();
  });

  it('shows the error message below the input', () => {
    render(<Input id="email" label="Email" error="Required" />);
    expect(screen.getByText('Required')).toBeInTheDocument();
  });

  it('adds border-danger class when there is an error', () => {
    render(<Input id="email" error="Bad input" />);
    expect(screen.getByRole('textbox')).toHaveClass('border-danger');
  });

  it('uses normal border when there is no error', () => {
    render(<Input id="email" />);
    expect(screen.getByRole('textbox')).not.toHaveClass('border-danger');
  });

  it('calls onChange when the user types', async () => {
    const onChange = vi.fn();
    render(<Input id="name" label="Name" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText('Name'), 'hi');
    expect(onChange).toHaveBeenCalled();
  });

  it('respects the disabled attribute', () => {
    render(<Input id="name" label="Name" disabled />);
    expect(screen.getByLabelText('Name')).toBeDisabled();
  });

  it('passes placeholder through', () => {
    render(<Input id="name" placeholder="Your name" />);
    expect(screen.getByPlaceholderText('Your name')).toBeInTheDocument();
  });

  it('renders a password input when type="password"', () => {
    render(<Input id="pwd" label="Password" type="password" />);
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  });
});
