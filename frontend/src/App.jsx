import { useState, useEffect } from 'react'
import { calculateSizing, fetchRetentionRecommendation } from './api'
import InputForm from './components/InputForm'
import ResultsPanel from './components/ResultsPanel'
import SizingChart from './components/SizingChart'

const DEFAULTS = {
  separator_type: 'vertical',
  phase_mode: '2-phase',
  gas_mmscfd: 5,
  oil_bopd: 1000,
  water_bpd: 200,
  api_gravity: 35,
  sg_gas: 0.65,
  sg_water: 1.0,
  pressure_psia: 800,
  temperature_f: 60,
  z_factor: 0.83,
  k_factor: 0.167,
  shell_height_ft: 10,
  liquid_fraction: 0.5,
  custom_retention: false,
  retention_oil_min: 1,
  retention_water_min: 3,
}

export default function App() {
  const [form, setForm] = useState(DEFAULTS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [retentionNote, setRetentionNote] = useState('')

  useEffect(() => {
    if (form.custom_retention) return
    fetchRetentionRecommendation(form.phase_mode, form.pressure_psia, form.temperature_f)
      .then((data) => {
        setRetentionNote(data.note || '')
        setForm((prev) => ({
          ...prev,
          retention_oil_min: data.oil_minutes,
          retention_water_min: data.water_minutes ?? data.oil_minutes,
        }))
      })
      .catch(() => {})
  }, [form.phase_mode, form.pressure_psia, form.temperature_f, form.custom_retention])

  const handleChange = (key, value) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value }
      if (key === 'separator_type') {
        next.k_factor = value === 'vertical' ? 0.167 : 0.45
      }
      return next
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const data = await calculateSizing(form)
      setResult(data)
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-petroleum-900 to-slate-950">
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">SeparatorSizer Pro</h1>
            <p className="mt-1 text-sm text-slate-400">
              2/3-phase separator design · UTM Ch.4 correlations
            </p>
          </div>
          <div className="hidden rounded-full border border-petroleum-500/40 bg-petroleum-700/30 px-4 py-1.5 text-xs text-petroleum-100 sm:block">
            Dr. Abdul Rahim Risal · Separator Part 3
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-[380px_1fr] sm:px-6">
        <InputForm
          form={form}
          onChange={handleChange}
          onSubmit={handleSubmit}
          loading={loading}
          retentionNote={retentionNote}
        />

        <div className="space-y-6">
          {error && (
            <div className="rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {result ? (
            <>
              <ResultsPanel result={result} form={form} />
              <SizingChart result={result} separatorType={form.separator_type} />
            </>
          ) : (
            <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 p-8 text-center">
              <div className="mb-4 rounded-full bg-petroleum-600/20 p-4">
                <svg className="h-10 w-10 text-petroleum-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-white">Enter feed conditions</h2>
              <p className="mt-2 max-w-md text-sm text-slate-400">
                Configure separator type, flow rates, and fluid properties, then run sizing to get vessel
                dimensions and capacity charts.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
