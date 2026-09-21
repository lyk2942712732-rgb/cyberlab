import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post } from '../api/http'
import type { User } from '../types'

export const useAuth = defineStore('auth', () => {
  const user = ref<User | null>(null)
  async function login(username: string, password: string) {
    const data = await post<{ access_token: string; user: User }>('/auth/login', { username, password })
    sessionStorage.setItem('cyberlab-token', data.access_token)
    user.value = data.user
  }
  async function load() { user.value = await get<User>('/auth/me') }
  function logout() { sessionStorage.removeItem('cyberlab-token'); user.value = null }
  return { user, login, load, logout }
})
