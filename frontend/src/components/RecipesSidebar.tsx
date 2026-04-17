import { useEffect, useState } from 'react'
import { recipesApi, StoredRecipe } from '../services/api'
import RecipeBuilder from './RecipeBuilder'
import './RecipesSidebar.css'

export default function RecipesSidebar() {
  const [recipes, setRecipes] = useState<StoredRecipe[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<StoredRecipe | null>(null)
  const [creating, setCreating] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setRecipes(await recipesApi.list())
    } catch {
      /* non-fatal */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSaved = (r: StoredRecipe) => {
    setRecipes((rs) => {
      const next = rs.filter((x) => x.id !== r.id)
      next.push(r)
      return next
    })
    setStatusMsg(`Saved “${r.name}”`)
    setTimeout(() => setStatusMsg(null), 3000)
  }

  const handleDelete = async (r: StoredRecipe) => {
    if (!confirm(`Delete recipe “${r.name}”?`)) return
    try {
      const updated = await recipesApi.remove(r.id)
      setRecipes(updated)
    } catch (e) {
      console.error(e)
    }
  }

  const handlePlay = async (r: StoredRecipe) => {
    try {
      setBusyId(r.id)
      setStatusMsg(null)
      const res = await recipesApi.play(r.id)
      setStatusMsg(`Playing ${res.track_count} tracks from “${r.name}”`)
      setTimeout(() => setStatusMsg(null), 4000)
    } catch (e: any) {
      setStatusMsg(e?.response?.data?.detail || 'Could not start playback')
    } finally {
      setBusyId(null)
    }
  }

  const handleMaterialize = async (r: StoredRecipe) => {
    const name = prompt(
      'Name for the new Spotify playlist:',
      `${r.name} (${new Date().toLocaleDateString()})`
    )
    if (!name) return
    try {
      setBusyId(r.id)
      const res = await recipesApi.materialize(r.id, { name })
      setStatusMsg(`Created playlist with ${res.track_count} tracks`)
      setTimeout(() => setStatusMsg(null), 5000)
    } catch (e: any) {
      setStatusMsg(e?.response?.data?.detail || 'Could not materialize')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="recipes-sidebar">
      <div className="recipes-header">
        <h3>Smart Filters</h3>
        <button className="new-recipe" onClick={() => setCreating(true)}>
          + New filter
        </button>
      </div>
      {statusMsg && <div className="recipes-status">{statusMsg}</div>}
      {loading ? (
        <div className="recipes-empty">Loading…</div>
      ) : recipes.length === 0 ? (
        <div className="recipes-empty">
          No saved filters yet. Build one with “New filter”.
        </div>
      ) : (
        <ul className="recipes-list">
          {recipes.map((r) => (
            <li key={r.id} className="recipe-row">
              <div className="recipe-row-name" title={`${r.buckets.length} bucket(s) • ${r.combine}`}>
                {r.name}
                <span className="recipe-row-meta">
                  {r.buckets.length} bucket{r.buckets.length !== 1 ? 's' : ''}
                </span>
              </div>
              <div className="recipe-row-actions">
                <button
                  onClick={() => handlePlay(r)}
                  disabled={busyId === r.id}
                  title="Resolve and play"
                >▶</button>
                <button
                  onClick={() => setEditing(r)}
                  title="Edit"
                >✎</button>
                <button
                  onClick={() => handleMaterialize(r)}
                  disabled={busyId === r.id}
                  title="Save as Spotify playlist"
                >＋</button>
                <button
                  onClick={() => handleDelete(r)}
                  title="Delete"
                  className="danger"
                >×</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <RecipeBuilder
        open={creating || !!editing}
        initial={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={handleSaved}
      />
    </div>
  )
}
