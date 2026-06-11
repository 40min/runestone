import security from 'eslint-plugin-security'

import baseConfig from './eslint.config.js'

export default [
  ...baseConfig,
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: {
      security,
    },
    rules: {
      'security/detect-eval-with-expression': 'error',
      'security/detect-new-buffer': 'error',
      'security/detect-non-literal-regexp': 'error',
    },
  },
]
