import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 30000 })
http.interceptors.request.use(config => {
  const token = sessionStorage.getItem('cyberlab-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
http.interceptors.response.use(response => response, error => {
  const message = error.response?.data?.error?.message || '网络连接失败，请稍后重试'
  ElMessage.error(typeof message === 'string' ? message : '请求失败')
  if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
    sessionStorage.removeItem('cyberlab-token')
    if (location.pathname !== '/login') location.assign('/login')
  }
  return Promise.reject(error)
})
export async function get<T>(url: string): Promise<T> { return (await http.get(url)).data.data }
export async function post<T>(url: string, data?: unknown): Promise<T> { return (await http.post(url, data)).data.data }
export async function put<T>(url: string, data?: unknown): Promise<T> { return (await http.put(url, data)).data.data }
export async function remove(url: string): Promise<void> { await http.delete(url) }
export default http
