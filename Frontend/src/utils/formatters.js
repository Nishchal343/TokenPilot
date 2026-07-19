export const currencyConfig = {
  locale: 'en-IN',
  currency: 'INR'
}

export const formatCurrency = value => new Intl.NumberFormat(currencyConfig.locale, {
  style: 'currency',
  currency: currencyConfig.currency,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
}).format(Number(value))
