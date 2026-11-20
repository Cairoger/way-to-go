import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
const styles = cva('btn', {
  variants: {
    variant: {
      default: 'btn-primary',
      outline: 'btn-secondary',
      ghost: 'btn-ghost',
      danger: 'btn-danger',
    },
  },
  defaultVariants: { variant: 'default' },
});
export function Button({
  className,
  variant,
  type = 'button',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof styles>) {
  return (
    <button type={type} className={twMerge(clsx(styles({ variant }), className))} {...props} />
  );
}
