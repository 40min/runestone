// No-op stand-in for `virtual:pwa-register/react` used when the PWA plugin is
// disabled (ordinary Vite development and Vitest). The real virtual module is
// provided by vite-plugin-pwa during production builds.
export type RegisterSWOptions = {
  onRegisterError?: (error: Error) => void;
};

export function useRegisterSW(options?: RegisterSWOptions) {
  void options;
  return {
    needRefresh: [false, () => {}] as [boolean, (value: boolean) => void],
    updateServiceWorker: (reloadPage?: boolean) => {
      void reloadPage;
    },
  };
}
