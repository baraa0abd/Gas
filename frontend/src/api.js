const API_BASE = import.meta.env.VITE_API_URL || ''

export async function calculateSizing(payload) {
  const res = await fetch(`${API_BASE}/api/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Calculation failed')
  return data.result
}

export async function fetchRetentionRecommendation(phaseMode, pressure, temperature) {
  const params = new URLSearchParams({
    phase_mode: phaseMode,
    pressure_psia: String(pressure),
    temperature_f: String(temperature),
  })
  const res = await fetch(`${API_BASE}/api/retention-recommendation?${params}`)
  return res.json()
}
