import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { errorMessage } from '../api/client.js'
import { getStations } from '../api/menu.js'
import { getMyOrders, getWaitTimes } from '../api/orders.js'
import { getStationStats } from '../api/reviews.js'
import Icon from '../components/Icon.jsx'
import { formatPrice, STATUS_LABEL } from '../format.js'

const STEPS = [
  { icon: 'mapPin', title: 'Chọn cửa hàng', text: 'Chọn chi nhánh gần tuyến đường của bạn, xem menu và thời gian chờ.' },
  { icon: 'card', title: 'Đặt & thanh toán', text: 'Thanh toán trực tuyến qua ví MoMo hoặc trả tiền mặt tại quầy.' },
  { icon: 'car', title: 'Lái xe tới nhận', text: 'Bấm "Tôi đã đến" khi vào làn xe, nhân viên mang món ra tận nơi.' },
]

const BENEFITS = [
  {
    icon: 'timer',
    title: 'Không phải xếp hàng chờ lâu',
    text: 'Đơn hàng được đưa thẳng vào bếp ngay khi xác nhận, rút ngắn tối đa thời gian dừng đỗ tại làn xe.',
    tone: 'tone-red',
  },
  {
    icon: 'car',
    title: 'Giao đúng xe theo biển số',
    text: 'Mỗi đơn hàng gắn với biển số xe của bạn giúp nhân viên nhận diện chính xác chỉ trong 3 giây.',
    tone: 'tone-amber',
  },
  {
    icon: 'check',
    title: 'Luôn nóng hổi khi nhận',
    text: 'Bếp căn thời gian chế biến hợp lý để thức ăn giữ trọn độ giòn và nóng ngay khi bạn tới quầy.',
    tone: 'tone-green',
  },
  {
    icon: 'star',
    title: 'Đánh giá & lắng nghe thật',
    text: 'Chấm điểm trực tiếp cho từng đơn hoàn thành giúp cửa hàng cải thiện chất lượng mỗi ngày.',
    tone: 'tone-blue',
  },
]

const FAQS = [
  {
    q: 'Làm sao nhân viên biết xe tôi đã đến làn nhận món?',
    a: 'Khi lái xe tới gần cửa hàng, bạn mở chi tiết đơn hàng và bấm nút "Tôi đã đến". Màn hình quầy sẽ lập tức đánh dấu nổi bật biển số xe của bạn để nhân viên mang món ra.',
  },
  {
    q: 'Tôi có thể hủy đơn hoặc đổi phương thức thanh toán không?',
    a: 'Có. Bạn hoàn toàn có thể hủy đơn hoặc đổi giữa MoMo và Tiền mặt trước khi bếp bắt đầu chế biến món. Nếu đã thanh toán qua MoMo, hệ thống sẽ hoàn tiền tự động về ví.',
  },
  {
    q: 'Món tại cửa hàng hết hàng thì sao?',
    a: 'Thực đơn hiển thị tình trạng còn/hết theo thời gian thực tại từng chi nhánh, giúp bạn không đặt nhầm món đã hết trong ngày.',
  },
]

// Các món "bay" quanh hình xe ở phần đầu trang
const HERO_FOODS = [
  { icon: 'burger', tone: 'burger' },
  { icon: 'cup', tone: 'drinks' },
  { icon: 'fries', tone: 'sides' },
  { icon: 'iceCream', tone: 'dessert' },
]

const ACTIVE = ['PENDING_PAYMENT', 'CONFIRMED', 'PREPARING', 'READY', 'ARRIVED']

export function isOpenNow(hours, now = new Date()) {
  if (!hours) return null
  if (/24\s*\/\s*7/.test(hours)) return true
  const m = hours.match(/(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})/)
  if (!m) return null
  const open = Number(m[1]) * 60 + Number(m[2])
  const close = Number(m[3]) * 60 + Number(m[4])
  const cur = now.getHours() * 60 + now.getMinutes()
  return open <= close ? cur >= open && cur < close : cur >= open || cur < close
}

function ActiveOrders() {
  const [orders, setOrders] = useState([])

  useEffect(() => {
    let cancelled = false
    getMyOrders()
      .then((list) => !cancelled && setOrders(list.filter((o) => ACTIVE.includes(o.status))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (orders.length === 0) return null

  return (
    <section className="active-orders">
      <h2>Đơn của bạn đang tiến hành</h2>
      <p className="active-hint">Theo dõi trạng thái đơn hàng hoặc báo "Tôi đã đến" khi xe tới làn.</p>
      <ul>
        {orders.slice(0, 3).map((o) => (
          <li key={o.id}>
            <Link to={`/orders/${o.id}`} className="active-order">
              <span>
                <strong>Đơn #{o.id}</strong> · {o.license_plate} · {formatPrice(o.total_amount)}
              </span>
              <span className={`status-pill status-${o.status.toLowerCase()}`}>
                {STATUS_LABEL[o.status]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {orders.length > 3 && (
        <Link to="/orders" className="active-more">
          Xem tất cả {orders.length} đơn <Icon name="arrowRight" size={16} />
        </Link>
      )}
    </section>
  )
}

function StationCard({ station, wait, rating }) {
  const open = isOpenNow(station.opening_hours)

  return (
    <Link to={`/stations/${station.id}`} className={`station-card${open === false ? ' station-closed' : ''}`}>
      <div className="station-top">
        <h2>{station.name}</h2>
        {open !== null && (
          <span className={`open-tag ${open ? 'open-yes' : 'open-no'}`}>
            {open ? 'Đang mở cửa' : 'Đã đóng cửa'}
          </span>
        )}
      </div>
      <p className="station-address">{station.address}</p>
      {station.opening_hours && (
        <p className="station-hours with-icon">
          <Icon name="clock" size={16} /> {station.opening_hours}
        </p>
      )}

      <div className="station-facts">
        <span className="with-icon" title="Ước tính cho đơn đặt bây giờ">
          <Icon name="timer" size={17} />
          <span>
            ~{wait?.estimated_minutes ?? 5} phút
            <small> · {wait?.queue_count ?? 0} đơn đang chờ</small>
          </span>
        </span>
        {rating && rating.total_reviews > 0 ? (
          <span className="station-rating with-icon">
            <Icon name="star" size={16} filled className="star-fill" />
            {rating.average_rating.toFixed(1)}
            <small>({rating.total_reviews})</small>
          </span>
        ) : (
          <span className="with-icon muted">
            <Icon name="star" size={16} className="star-empty" /> Chưa có đánh giá
          </span>
        )}
      </div>
      <span className="station-cta">
        {open === false ? 'Xem menu (đặt trước)' : 'Xem menu & đặt món'} <Icon name="arrowRight" size={17} />
      </span>
    </Link>
  )
}

export default function StationsPage() {
  const [stations, setStations] = useState(null)
  const [waits, setWaits] = useState({})
  const [ratings, setRatings] = useState({})
  const [query, setQuery] = useState('')
  const [onlyOpen, setOnlyOpen] = useState(false)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError('')
    setStations(null)
    getStations()
      .then((data) => {
        if (cancelled) return
        setStations(data)
        Promise.all(
          data.map((s) =>
            getStationStats(s.id)
              .then((r) => [s.id, r])
              .catch(() => [s.id, null]),
          ),
        ).then((pairs) => !cancelled && setRatings(Object.fromEntries(pairs)))
      })
      .catch((err) => !cancelled && setError(errorMessage(err)))
    getWaitTimes()
      .then((list) => !cancelled && setWaits(Object.fromEntries(list.map((w) => [w.station_id, w]))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const shown = useMemo(() => {
    if (!stations) return []
    const q = query.trim().toLowerCase()
    return stations
      .filter((s) => !q || `${s.name} ${s.address}`.toLowerCase().includes(q))
      .filter((s) => !onlyOpen || isOpenNow(s.opening_hours) !== false)
      .sort((a, b) => {
        const oa = isOpenNow(a.opening_hours) === false ? 1 : 0
        const ob = isOpenNow(b.opening_hours) === false ? 1 : 0
        if (oa !== ob) return oa - ob
        return (waits[a.id]?.queue_count ?? 0) - (waits[b.id]?.queue_count ?? 0)
      })
  }, [stations, query, onlyOpen, waits])

  return (
    <>
      <ActiveOrders />

      {/* 1. HERO BANNER CÓ ẢNH CHỤP THỰC TẾ */}
      <section className="hero hero-home">
        <div className="hero-content">
          <span className="hero-pill">🚗 GoLane Drive-Thru · Đặt trước trên Web</span>
          <h1>Đặt trước, lái xe qua, nhận món nóng hổi tức thì</h1>
          <p className="hero-desc">
            Chọn chi nhánh thuận đường nhất, gọi món và thanh toán ngay trên web. Khi tới làn xe,
            chỉ cần chạm nhẹ <strong>"Tôi đã đến"</strong>, nhân viên sẽ mang bữa ăn ra tận cửa xe.
          </p>
          <div className="hero-actions">
            <a href="#stations" className="btn">Chọn cửa hàng & đặt món</a>
            <a href="#about" className="btn btn-ghost">Tìm hiểu GoLane</a>
          </div>
          <div className="hero-stats-row">
            <div><strong>3+</strong><span>Chi nhánh TP.HCM</span></div>
            <div><strong>~60s</strong><span>Nhận món tại làn</span></div>
            <div><strong>100%</strong><span>Nóng hổi tươi mới</span></div>
          </div>
        </div>

        <div className="hero-visual">
          <img
            src="/images/hero-drivethru.jpg"
            alt="Nhận món trực tiếp tại làn xe GoLane Drive-Thru"
            className="hero-photo"
          />
          <div className="hero-floating-tag">
            <Icon name="check" size={16} />
            <span>Giao đúng xe theo biển số đã đặt</span>
          </div>
        </div>
      </section>

      {/* 2. QUY TRÌNH 3 BƯỚC */}
      <section className="steps-strip">
        {STEPS.map((s, i) => (
          <div key={s.title} className="step-pill-card hover-lift">
            <span className="step-icon">
              <Icon name={s.icon} size={20} />
            </span>
            <div>
              <strong>{i + 1}. {s.title}</strong>
              <p>{s.text}</p>
            </div>
          </div>
        ))}
      </section>

      {/* 3. DANH SÁCH CỬA HÀNG */}
      <section id="stations" className="home-section">
        <div className="stations-head">
          <div>
            <p className="dash-eyebrow">Hệ thống chi nhánh</p>
            <h2>Chọn cửa hàng gần bạn {stations && <span className="muted">({shown.length})</span>}</h2>
          </div>
          <div className="stations-filter">
            <label className="search-box">
              <Icon name="search" size={17} />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Tìm theo tên hoặc địa chỉ..."
                aria-label="Tìm cửa hàng"
              />
            </label>
            <label className="check">
              <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
              Chỉ quán đang mở
            </label>
          </div>
        </div>

        {error && (
          <div className="state">
            <p className="error-text">{error}</p>
            <button className="btn" onClick={() => setReloadKey((k) => k + 1)}>
              Thử lại
            </button>
          </div>
        )}

        {!error && stations === null && <div className="state">Đang tải danh sách cửa hàng…</div>}

        {stations?.length === 0 && (
          <div className="state">Hiện chưa có cửa hàng nào đang hoạt động.</div>
        )}

        {stations?.length > 0 && shown.length === 0 && (
          <div className="state">Không tìm thấy cửa hàng phù hợp.</div>
        )}

        {shown.length > 0 && (
          <ul className="station-grid">
            {shown.map((station) => (
              <li key={station.id}>
                <StationCard station={station} wait={waits[station.id]} rating={ratings[station.id]} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 4. ABOUT GOLANE (GIỚI THIỆU THƯƠNG HIỆU + ẢNH BẾP) */}
      <section id="about" className="home-section about-section">
        <div className="about-image-box hover-lift">
          <img
            src="/images/about-kitchen.jpg"
            alt="Burger bò phô mai, khoai tây chiên và nước ngọt tươi mới tại bếp GoLane"
          />
        </div>
        <div className="about-content">
          <p className="dash-eyebrow">About GoLane</p>
          <h2>Bữa ăn chuẩn vị, sẵn sàng ngay khi xe bạn lăn bánh tới</h2>
          <p>
            GoLane ra đời với sứ mệnh giải phóng khách hàng khỏi cảnh xếp hàng dài mệt mỏi tại các
            cửa hàng đồ ăn nhanh truyền thống. Mỗi phần burger, gà rán và thức uống đều được chế
            biến tươi mới ngay sau khi bạn đặt trên ứng dụng.
          </p>
          <ul className="about-checklist">
            <li><Icon name="check" size={16} /> Nguyên liệu tươi sạch mỗi ngày, chế biến tại chỗ</li>
            <li><Icon name="check" size={16} /> Đóng gói chắc chắn, tiện mang theo khi lái xe</li>
            <li><Icon name="check" size={16} /> Cập nhật tình trạng món còn/hết theo từng chi nhánh</li>
          </ul>
          <a href="#stations" className="btn">Đặt món tại chi nhánh gần nhất</a>
        </div>
      </section>

      {/* 5. BANNER THỰC ĐƠN NỔI BẬT */}
      <section id="combo-promo" className="home-section promo-banner">
        <div className="promo-text">
          <span className="promo-tag">🔥 Thực đơn bán chạy</span>
          <h2>Combo Gà Giòn & Burger Phô Mai</h2>
          <p>
            Thưởng thức bộ đôi Burger bò nướng phô mai tan chảy, Gà rán giòn rụm cùng Trà đào cam sả
            mát lạnh. Đặt trước ngay để tiết kiệm tới 15 phút chờ đợi giờ cao điểm!
          </p>
          <a href="#stations" className="btn promo-btn">Khám phá thực đơn ngay</a>
        </div>
        <div className="promo-img-wrap">
          <img
            src="/images/promo-combo.jpg"
            alt="Combo gà rán, burger phô mai, khoai tây chiên và trà đào GoLane"
          />
        </div>
      </section>

      {/* 6. LÝ DO CHỌN GOLANE */}
      <section id="why-golane" className="home-section">
        <div className="section-head">
          <p className="dash-eyebrow">Trải nghiệm khác biệt</p>
          <h2>Tại sao khách hàng yêu thích GoLane Drive-Thru?</h2>
        </div>
        <div className="benefit-grid">
          {BENEFITS.map((b) => (
            <article key={b.title} className={`benefit-card hover-lift ${b.tone}`}>
              <span className="benefit-icon">
                <Icon name={b.icon} size={22} />
              </span>
              <h3>{b.title}</h3>
              <p>{b.text}</p>
            </article>
          ))}
        </div>
      </section>

      {/* 7. CÂU HỎI THƯỜNG GẶP */}
      <section id="faq" className="home-section">
        <div className="section-head">
          <p className="dash-eyebrow">Giải đáp nhanh</p>
          <h2>Câu hỏi thường gặp</h2>
        </div>
        <div className="faq-grid">
          {FAQS.map((item) => (
            <article key={item.q} className="faq-card hover-lift">
              <h3>{item.q}</h3>
              <p>{item.a}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
