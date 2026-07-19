import type {
  ExportResult,
  ImageInfo,
  LabelDef,
  LabelMeDoc,
  ProjectMeta,
  ProjectSummary,
} from './types'

const USER_KEY = 'aiops.annotate.user'

export function getCurrentUser(): string {
  return localStorage.getItem(USER_KEY) ?? ''
}

export function setCurrentUser(name: string) {
  localStorage.setItem(USER_KEY, name)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Annotate-User': getCurrentUser(),
      ...options.headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  listUsers: () => request<string[]>('/api/users'),
  createUser: (name: string) =>
    request<string[]>('/api/users', { method: 'POST', body: JSON.stringify({ name }) }),

  listProjects: () => request<ProjectSummary[]>('/api/projects'),
  createProject: (name: string, imagesDir: string) =>
    request<ProjectMeta>('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name, images_dir: imagesDir }),
    }),
  getProject: (name: string) => request<ProjectMeta>(`/api/projects/${enc(name)}`),
  setLabels: (name: string, labels: LabelDef[]) =>
    request<ProjectMeta>(`/api/projects/${enc(name)}/labels`, {
      method: 'PUT',
      body: JSON.stringify({ labels }),
    }),

  listImages: (name: string) => request<ImageInfo[]>(`/api/projects/${enc(name)}/images`),
  imageUrl: (name: string, filename: string) =>
    `/api/projects/${enc(name)}/images/${enc(filename)}`,

  assign: (name: string, users: string[], keepExisting: boolean) =>
    request<ProjectMeta>(`/api/projects/${enc(name)}/assign`, {
      method: 'POST',
      body: JSON.stringify({ users, mode: 'round_robin', keep_existing: keepExisting }),
    }),
  reassign: (name: string, filename: string, user: string) =>
    request<ProjectMeta>(`/api/projects/${enc(name)}/assign`, {
      method: 'PUT',
      body: JSON.stringify({ filename, user }),
    }),

  getAnnotation: (name: string, filename: string) =>
    request<LabelMeDoc>(`/api/projects/${enc(name)}/annotations/${enc(filename)}`),
  saveAnnotation: (name: string, filename: string, doc: LabelMeDoc) =>
    request<{ saved: boolean }>(`/api/projects/${enc(name)}/annotations/${enc(filename)}`, {
      method: 'PUT',
      body: JSON.stringify(doc),
    }),

  export: (
    name: string,
    outputDir: string,
    ratios: { train: number; val: number; test: number },
    seed: number | null,
  ) =>
    request<ExportResult>(`/api/projects/${enc(name)}/export`, {
      method: 'POST',
      body: JSON.stringify({
        output_dir: outputDir,
        format: 'labelme',
        train_ratio: ratios.train,
        val_ratio: ratios.val,
        test_ratio: ratios.test,
        seed,
      }),
    }),
}

const enc = encodeURIComponent
