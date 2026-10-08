export interface User { id: string; username: string; real_name: string; student_number: string | null; role: 'STUDENT' | 'ADMIN' }
export interface Lesson { id: string; chapter_id: string; title: string; content?: string; sort_order: number; status: string; related_lab_id: string | null; course_id?: string }
export interface Chapter { id: string; course_id: string; title: string; sort_order: number; lessons: Lesson[] }
export interface Course { id: string; name: string; description: string; status: string; chapters: Chapter[] }
export interface Lab { id: string; name: string; description: string; objective: string; steps: string; category: string; difficulty: string; target_image_id: string; target_port: number; duration_minutes: number; cpu_limit: number; memory_limit: number; status: string; flag?: string; writeup?: string }
export interface LabWriteup { schema_version: number; lab_id: string; title: string; format: 'markdown'; content: string; updated_at: string }
export interface Instance { id: string; runtime_id: string; instance_type: string; status: string; ip_address: string }
export interface LabSession { id: string; user_id: string; lab_template_id: string; lab_name: string; lab: Lab; status: string; target_ip: string | null; started_at: string; expires_at: string; finished_at: string | null; error: string | null; instances: Instance[]; student?: User }
export interface Score { lab_id: string; lab_name: string; score: number | null; score_session_id?: string | null; flag_score?: number; completed: boolean; completed_at: string | null; submissions_count: number; attempted: boolean }
export interface Progress { id: string; user_id: string; lesson_id: string; completed: boolean; completed_at: string; lesson_title?: string; chapter_title?: string; course_name?: string }
export interface TargetImage { id: string; display_name: string; repository: string; tag: string; image_id: string | null; repo_digest: string | null; size_bytes: number; original_filename: string; status: string; created_at: string; updated_at: string; error_message: string | null }
export interface StudentStats extends User { completed_labs: number; average_score: number | null; last_completed_at: string | null }
export const activeStatuses = ['CREATING', 'STARTING', 'READY', 'RESETTING', 'STOPPING', 'FINISHED']
export const date = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
export const difficulty: Record<string, string> = { BEGINNER: '入门', INTERMEDIATE: '进阶', ADVANCED: '挑战' }
