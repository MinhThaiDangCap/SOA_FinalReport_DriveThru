import { useCallback, useEffect, useState } from 'react'

import { errorMessage } from '../../api/client.js'
import {
  createCategory,
  createItem,
  deleteCategory,
  getCategories,
  getItems,
  updateCategory,
  updateItem,
} from '../../api/menu.js'
import { categoryStyle } from '../../categoryStyle.js'
import { formatPrice } from '../../format.js'
import Icon from '../Icon.jsx'

const EMPTY_ITEM = { category_id: '', name: '', description: '', price: '', image_url: '', is_active: true }

function ItemForm({ initial, categories, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState({ ...EMPTY_ITEM, ...initial })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSubmit({
        category_id: Number(form.category_id),
        name: form.name,
        description: form.description || null,
        price: Number(form.price),
        image_url: form.image_url || null,
        is_active: form.is_active,
      })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <form className="form panel-form" onSubmit={handleSubmit}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-row">
        <label className="field">
          Tên món
          <input value={form.name} onChange={set('name')} required maxLength={100} />
        </label>
        <label className="field">
          Danh mục
          <select value={form.category_id} onChange={set('category_id')} required>
            <option value="">-- Chọn --</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Giá (VND)
          <input type="number" min={0} step={1000} value={form.price} onChange={set('price')} required />
        </label>
      </div>
      <label className="field">
        Mô tả
        <input value={form.description || ''} onChange={set('description')} maxLength={500} />
      </label>
      <label className="field">
        Link ảnh
        <input value={form.image_url || ''} onChange={set('image_url')} placeholder="https://..." maxLength={500} />
      </label>
      <label className="check">
        <input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> Đang bán
      </label>
      <div className="form-actions">
        <button type="submit" className="btn" disabled={busy}>{busy ? 'Đang lưu...' : submitLabel}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Hủy</button>
      </div>
    </form>
  )
}

function CategoryPanel({ categories, onChanged }) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [renaming, setRenaming] = useState(null)

  async function run(fn) {
    setError('')
    try {
      await fn()
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <section className="panel-box">
      <h2 className="panel-title">Danh mục</h2>
      {error && <div className="form-error" role="alert">{error}</div>}
      <ul className="chip-list">
        {categories.map((c) =>
          renaming?.id === c.id ? (
            <li key={c.id}>
              <form
                className="inline-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  run(() => updateCategory(c.id, { name: renaming.name, sort_order: c.sort_order })).then(() => setRenaming(null))
                }}
              >
                <input value={renaming.name} onChange={(e) => setRenaming({ ...renaming, name: e.target.value })} required />
                <button type="submit" className="btn btn-small">Lưu</button>
                <button type="button" className="btn btn-ghost btn-small" onClick={() => setRenaming(null)}>Hủy</button>
              </form>
            </li>
          ) : (
            <li key={c.id} className="chip">
              {c.name}
              <button type="button" className="link-btn" onClick={() => setRenaming({ id: c.id, name: c.name })}>sửa</button>
              <button
                type="button"
                className="link-btn"
                onClick={() => window.confirm(`Xóa danh mục "${c.name}"?`) && run(() => deleteCategory(c.id))}
              >
                xóa
              </button>
            </li>
          ),
        )}
      </ul>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault()
          run(() => createCategory({ name, sort_order: categories.length + 1 })).then(() => setName(''))
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên danh mục mới" required />
        <button type="submit" className="btn btn-small">+ Thêm</button>
      </form>
    </section>
  )
}

export default function MenuTab() {
  const [categories, setCategories] = useState([])
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('all')
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    Promise.all([getCategories(), getItems({ include_inactive: true })])
      .then(([cats, its]) => {
        setCategories(cats)
        setItems(its)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load])

  async function save(id, body) {
    if (id === 'new') await createItem(body)
    else await updateItem(id, body)
    setEditing(null)
    load()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!items) return <div className="state">Đang tải thực đơn...</div>

  const catName = Object.fromEntries(categories.map((c) => [c.id, c.name]))
  const shown = filter === 'all' ? items : items.filter((i) => i.category_id === filter)

  return (
    <div>
      <CategoryPanel categories={categories} onChanged={load} />

      <div className="panel-toolbar">
        <div className="category-tabs">
          <button type="button" className={filter === 'all' ? 'tab active' : 'tab'} onClick={() => setFilter('all')}>
            Tất cả ({items.length})
          </button>
          {categories.map((c) => (
            <button key={c.id} type="button" className={filter === c.id ? 'tab active' : 'tab'} onClick={() => setFilter(c.id)}>
              <Icon name={categoryStyle(c.name).icon} size={16} />
              {c.name}
            </button>
          ))}
        </div>
        {editing !== 'new' && (
          <button type="button" className="btn btn-small" onClick={() => setEditing('new')}>+ Thêm món</button>
        )}
      </div>
      <p className="panel-hint">Món tắt "Đang bán" sẽ biến mất khỏi mọi cửa hàng. Muốn báo hết món tạm thời ở một cửa hàng thì nhân viên tắt ở màn hình quầy.</p>

      {editing === 'new' && (
        <ItemForm
          initial={{ category_id: filter === 'all' ? '' : filter }}
          categories={categories}
          submitLabel="Tạo món"
          onSubmit={(b) => save('new', b)}
          onCancel={() => setEditing(null)}
        />
      )}

      <ul className="admin-list">
        {shown.map((item) => (
          <li key={item.id}>
            {editing === item.id ? (
              <ItemForm initial={item} categories={categories} submitLabel="Lưu" onSubmit={(b) => save(item.id, b)} onCancel={() => setEditing(null)} />
            ) : (
              <div className={`admin-row${item.is_active ? '' : ' row-off'}`}>
                <div className="admin-item">
                  {item.image_url ? (
                    <img src={item.image_url} alt="" />
                  ) : (
                    <span className={`admin-thumb tone-${categoryStyle(catName[item.category_id]).tone}`}>
                      <Icon name={categoryStyle(catName[item.category_id]).icon} size={24} />
                    </span>
                  )}
                  <div>
                    <strong>{item.name}</strong> · {formatPrice(item.price)}
                    {!item.is_active && <span className="tag-bad"> ngừng bán</span>}
                    <p className="muted">{catName[item.category_id] || 'Không rõ danh mục'}{item.description ? ` · ${item.description}` : ''}</p>
                  </div>
                </div>
                <button type="button" className="btn btn-ghost btn-small" onClick={() => setEditing(item.id)}>Sửa</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
