export const convertToNumber = (value: any, defaultValue: number = 0): number => {
  if (value === null || value === undefined) return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
};

export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(value);
};

export const formatPercentage = (value: number, decimals: number = 2): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

export const bucketDateByMonth = (date: Date, timezone: string = 'America/Denver'): string => {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit'
  }).format(date).replace('/', '-');
};