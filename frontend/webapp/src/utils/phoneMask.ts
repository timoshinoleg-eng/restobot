/**
 * Russian phone mask utilities.
 * Accepts +7, 8, or plain 10-digit input.
 */

export function formatPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  let withoutCountry = digits;

  // Drop leading 7 or 8 country code
  if (withoutCountry.startsWith('8') || withoutCountry.startsWith('7')) {
    withoutCountry = withoutCountry.substring(1);
  }

  // Limit to 10 digits
  withoutCountry = withoutCountry.substring(0, 10);

  let result = '+7';
  if (withoutCountry.length > 0) result += ` (${withoutCountry.substring(0, 3)}`;
  if (withoutCountry.length >= 3) result += `)`;
  if (withoutCountry.length > 3) result += ` ${withoutCountry.substring(3, 6)}`;
  if (withoutCountry.length > 6) result += `-${withoutCountry.substring(6, 8)}`;
  if (withoutCountry.length > 8) result += `-${withoutCountry.substring(8, 10)}`;

  return result;
}

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

export function isValidPhone(value: string): boolean {
  const digits = digitsOnly(value);
  if (digits.length === 11 && (digits.startsWith('7') || digits.startsWith('8'))) return true;
  if (digits.length === 10) return true;
  return false;
}
