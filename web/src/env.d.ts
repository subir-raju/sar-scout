/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Address of the Python API */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}