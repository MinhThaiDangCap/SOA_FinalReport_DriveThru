import React, { useState, useEffect } from "react";
import axios from "axios";

const AUTH_API = import.meta.env.VITE_AUTH_API || "http://localhost:8001";
const FEEDBACK_API = import.meta.env.VITE_FEEDBACK_API || "http://localhost:8002";

const INITIAL_ORDERS = [
  {
    id: 1007,
    customer_name: "Nguyễn Hữu Tân",
    license_plate: "51K-888.99",
    station_id: 1,
    items: ["2x Burger Bò Phô Mai", "1x Khoai Tây Chiên Lớn", "2x Coca-Cola"],
    total_amount: 185000,
    payment_method: "VNPAY (Đã thanh toán)",
    status: "CONFIRMED",
    created_at: "10:15",
  },
  {
    id: 1008,
    customer_name: "Trần Minh Khoa",
    license_plate: "59A-123.45",
    station_id: 1,
    items: ["1x Combo Gà Giòn Cay", "1x Trà Đào Cam Sả"],
    total_amount: 119000,
    payment_method: "Tại quầy (Thu tiền khi giao)",
    status: "PREPARING",
    created_at: "10:12",
  },
  {
    id: 1009,
    customer_name: "Lê Hoàng Nam",
    license_plate: "60A-567.89",
    station_id: 1,
    items: ["3x Gà Rán Giòn", "2x Burger Tôm", "3x Pepsi"],
    total_amount: 265000,
    payment_method: "VNPAY (Đã thanh toán)",
    status: "READY",
    created_at: "10:08",
  },
  {
    id: 1010,
    customer_name: "Phạm Thanh Hà",
    license_plate: "51H-999.99",
    station_id: 1,
    items: ["1x Burger Gà Quay", "1x Súp Nấm"],
    total_amount: 95000,
    payment_method: "Tại quầy (Thu tiền khi giao)",
    status: "ARRIVED",
    created_at: "10:05",
  },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("drivethru_token") || "");
  const [activeTab, setActiveTab] = useState("staff"); // "staff" | "admin" | "customer" | "login"

  // Login / Register state
  const [authMode, setAuthMode] = useState("login");
  const [email, setEmail] = useState("admin@drivethru.vn");
  const [password, setPassword] = useState("Password123");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [authMsg, setAuthMsg] = useState("");

  // Staff Queue state
  const [orders, setOrders] = useState(INITIAL_ORDERS);

  // Admin Feedback Analytics state
  const [selectedStation, setSelectedStation] = useState(1);
  const [stats, setStats] = useState({
    station_id: 1,
    total_reviews: 0,
    average_rating: 0,
    rating_breakdown: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    negative_reviews: [],
  });
  const [allReviews, setAllReviews] = useState([]);

  // Admin Staff Management state
  const [staffList, setStaffList] = useState([]);
  const [newStaff, setNewStaff] = useState({
    email: "",
    password: "Password123",
    full_name: "",
    phone: "",
    station_id: 1,
  });
  const [staffMsg, setStaffMsg] = useState("");

  // Customer Review & Telegram Link state
  const [telegramLink, setTelegramLink] = useState(null);
  const [reviewForm, setReviewForm] = useState({
    order_id: 1011,
    station_id: 1,
    rating: 5,
    comment: "",
  });
  const [reviewMsg, setReviewMsg] = useState("");

  // Fetch current user if token exists
  useEffect(() => {
    if (token) {
      axios
        .get(`${AUTH_API}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        .then((res) => {
          setUser(res.data);
          if (res.data.role === "admin") setActiveTab("admin");
          else if (res.data.role === "staff") setActiveTab("staff");
          else setActiveTab("customer");
        })
        .catch(() => {
          setToken("");
          localStorage.removeItem("drivethru_token");
        });
    }
  }, [token]);

  // Fetch Feedback stats when selectedStation changes
  const fetchFeedbackData = async (stationId = selectedStation) => {
    try {
      const [statsRes, listRes] = await Promise.all([
        axios.get(`${FEEDBACK_API}/api/reviews/stations/${stationId}/stats`),
        axios.get(`${FEEDBACK_API}/api/reviews/stations/${stationId}`),
      ]);
      setStats(statsRes.data);
      setAllReviews(listRes.data);
    } catch (err) {
      console.warn("Chưa kết nối được feedback-service:", err.message);
    }
  };

  const fetchStaffList = async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${AUTH_API}/api/auth/staff`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStaffList(res.data);
    } catch (err) {
      console.warn("Không lấy được danh sách staff:", err.message);
    }
  };

  useEffect(() => {
    fetchFeedbackData(selectedStation);
  }, [selectedStation]);

  useEffect(() => {
    if (user?.role === "admin") {
      fetchStaffList();
    }
  }, [user, token]);

  // Quick Login helper
  const handleQuickLogin = async (quickEmail) => {
    setEmail(quickEmail);
    setPassword("Password123");
    setAuthMsg("Đang đăng nhập...");
    try {
      const res = await axios.post(`${AUTH_API}/api/auth/login`, {
        email: quickEmail,
        password: "Password123",
      });
      const accessToken = res.data.access_token;
      localStorage.setItem("drivethru_token", accessToken);
      setToken(accessToken);
      setUser(res.data.user);
      setAuthMsg("");
    } catch (err) {
      setAuthMsg(err.response?.data?.detail || "Không kết nối được auth-service (cổng 8001)");
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthMsg("");
    try {
      if (authMode === "register") {
        await axios.post(`${AUTH_API}/api/auth/register`, {
          email,
          password,
          full_name: fullName,
          phone,
        });
        setAuthMsg("✅ Đăng ký thành công! Đang tự động đăng nhập...");
      }
      const res = await axios.post(`${AUTH_API}/api/auth/login`, { email, password });
      localStorage.setItem("drivethru_token", res.data.access_token);
      setToken(res.data.access_token);
      setUser(res.data.user);
    } catch (err) {
      setAuthMsg("❌ " + (err.response?.data?.detail || "Lỗi kết nối tới auth-service"));
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("drivethru_token");
    setToken("");
    setUser(null);
    setTelegramLink(null);
    setActiveTab("login");
  };

  // Staff Queue transitions
  const advanceOrderStatus = (orderId, nextStatus) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: nextStatus } : o))
    );
  };

  // Admin Create Staff
  const handleCreateStaff = async (e) => {
    e.preventDefault();
    setStaffMsg("");
    try {
      await axios.post(`${AUTH_API}/api/auth/staff`, newStaff, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStaffMsg("✅ Đã tạo tài khoản nhân viên thành công! Kiểm tra ngay trong TablePlus.");
      setNewStaff({
        email: "",
        password: "Password123",
        full_name: "",
        phone: "",
        station_id: 1,
      });
      fetchStaffList();
    } catch (err) {
      setStaffMsg("❌ " + (err.response?.data?.detail || "Lỗi khi tạo nhân viên"));
    }
  };

  const handleToggleStaff = async (staffId) => {
    try {
      await axios.patch(
        `${AUTH_API}/api/auth/staff/${staffId}/toggle-active`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchStaffList();
    } catch (err) {
      alert(err.response?.data?.detail || "Lỗi cập nhật trạng thái");
    }
  };

  // Customer Telegram Link
  const handleGetTelegramLink = async () => {
    try {
      const res = await axios.post(
        `${AUTH_API}/api/auth/telegram/link-token`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setTelegramLink(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || "Vui lòng đăng nhập trước khi lấy link Telegram!");
    }
  };

  // Customer Submit Review
  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    setReviewMsg("");
    try {
      await axios.post(`${FEEDBACK_API}/api/reviews`, reviewForm, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setReviewMsg("✅ Gửi đánh giá thành công! Dữ liệu đã lưu vào feedback_db.");
      setReviewForm((prev) => ({
        ...prev,
        order_id: prev.order_id + 1,
        comment: "",
      }));
      fetchFeedbackData(selectedStation);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setReviewMsg("❌ " + detail.map((d) => d.msg).join(", "));
      } else {
        setReviewMsg("❌ " + (detail || "Lỗi khi gửi đánh giá"));
      }
    }
  };

  return (
    <div>
      {/* TOP NAVBAR */}
      <nav className="navbar">
        <div className="brand">
          <span>🚗 DRIVE-THRU SOA SYSTEM</span>
          <span
            className="badge"
            style={{ background: "rgba(249, 115, 22, 0.15)", color: "#fb923c" }}
          >
            Microservices · FastAPI · PostgreSQL
          </span>
        </div>

        <div className="nav-links">
          <button
            className={`btn ${activeTab === "staff" ? "btn-primary" : "btn-outline"}`}
            onClick={() => setActiveTab("staff")}
          >
            👨‍🍳 Dashboard Nhân Viên (Bếp & Làn Xe)
          </button>
          <button
            className={`btn ${activeTab === "admin" ? "btn-primary" : "btn-outline"}`}
            onClick={() => setActiveTab("admin")}
          >
            📊 Dashboard Admin (Thống Kê & Nhân Sự)
          </button>
          <button
            className={`btn ${activeTab === "customer" ? "btn-primary" : "btn-outline"}`}
            onClick={() => setActiveTab("customer")}
          >
            ⭐ Khách Đánh Giá & Telegram Bot
          </button>
          <button
            className={`btn ${activeTab === "login" ? "btn-primary" : "btn-outline"}`}
            onClick={() => setActiveTab("login")}
          >
            🔐 {user ? `${user.full_name} (${user.role.toUpperCase()})` : "Đăng Nhập"}
          </button>
          {user && (
            <button className="btn btn-danger" onClick={handleLogout}>
              Đăng xuất
            </button>
          )}
        </div>
      </nav>

      <div className="container">
        {/* BANNER TRẠNG THÁI ĐĂNG NHẬP */}
        <div
          className="card"
          style={{
            marginBottom: "1.5rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
            background: "linear-gradient(90deg, #1e293b 0%, #0f172a 100%)",
          }}
        >
          <div>
            <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
              Đổi nhanh tài khoản Demo (1-Click Login với <b>auth-service</b>):
            </div>
            <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
              <button
                className="btn btn-outline"
                onClick={() => handleQuickLogin("admin@drivethru.vn")}
              >
                👑 Admin (admin@drivethru.vn)
              </button>
              <button
                className="btn btn-outline"
                onClick={() => handleQuickLogin("staff1@drivethru.vn")}
              >
                👨‍🍳 NV Trạm #1 (staff1@drivethru.vn)
              </button>
              <button
                className="btn btn-outline"
                onClick={() => handleQuickLogin("khachhang@drivethru.vn")}
              >
                🧑 Khách hàng (khachhang@drivethru.vn)
              </button>
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            {user ? (
              <div>
                <div style={{ fontWeight: 700, color: "#22c55e" }}>
                  ● Đã xác thực JWT: {user.full_name}
                </div>
                <div style={{ fontSize: "0.82rem", color: "#94a3b8" }}>
                  Email: {user.email} | Role: <b>{user.role.toUpperCase()}</b>
                  {user.station_id ? ` | Trạm #${user.station_id}` : ""}
                </div>
              </div>
            ) : (
              <div style={{ color: "#eab308", fontSize: "0.9rem" }}>
                ⚠️ Chưa đăng nhập — Bấm 1 trong 3 nút bên trái để nhận JWT Token ngay!
              </div>
            )}
          </div>
        </div>

        {/* ==================== TAB 1: DASHBOARD NHÂN VIÊN ==================== */}
        {activeTab === "staff" && (
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "1.25rem",
              }}
            >
              <div>
                <h2>👨‍🍳 Màn Hình Điều Phối Đơn Hàng Drive-Thru (Trạm #{user?.station_id || 1})</h2>
                <p style={{ color: "#94a3b8", fontSize: "0.9rem", marginTop: "0.25rem" }}>
                  Nhân viên theo dõi đơn theo thời gian thực, chuẩn bị món và nhìn biển số xe tại làn ARRIVED để giao đúng khách.
                </p>
              </div>
            </div>

            <div className="grid-4">
              {/* CỘT 1: CONFIRMED */}
              <div className="card">
                <h3 style={{ color: "#3b82f6", marginBottom: "1rem" }}>
                  1. ĐÃ XÁC NHẬN (CONFIRMED)
                </h3>
                {orders
                  .filter((o) => o.status === "CONFIRMED")
                  .map((order) => (
                    <div
                      key={order.id}
                      className="card"
                      style={{ marginBottom: "0.85rem", background: "#0f172a" }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <b>Đơn #{order.id}</b>
                        <span className="plate-badge">{order.license_plate}</span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "0.5rem 0" }}>
                        Khách: {order.customer_name} ({order.created_at})
                      </div>
                      <ul style={{ fontSize: "0.85rem", paddingLeft: "1.1rem", marginBottom: "0.75rem" }}>
                        {order.items.map((it, idx) => (
                          <li key={idx}>{it}</li>
                        ))}
                      </ul>
                      <button
                        className="btn btn-primary"
                        style={{ width: "100%" }}
                        onClick={() => advanceOrderStatus(order.id, "PREPARING")}
                      >
                        🔥 Nhận làm món (PREPARING)
                      </button>
                    </div>
                  ))}
              </div>

              {/* CỘT 2: PREPARING */}
              <div className="card">
                <h3 style={{ color: "#eab308", marginBottom: "1rem" }}>
                  2. BẾP ĐANG LÀM (PREPARING)
                </h3>
                {orders
                  .filter((o) => o.status === "PREPARING")
                  .map((order) => (
                    <div
                      key={order.id}
                      className="card"
                      style={{ marginBottom: "0.85rem", background: "#0f172a" }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <b>Đơn #{order.id}</b>
                        <span className="plate-badge">{order.license_plate}</span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "0.5rem 0" }}>
                        Khách: {order.customer_name}
                      </div>
                      <ul style={{ fontSize: "0.85rem", paddingLeft: "1.1rem", marginBottom: "0.75rem" }}>
                        {order.items.map((it, idx) => (
                          <li key={idx}>{it}</li>
                        ))}
                      </ul>
                      <button
                        className="btn btn-primary"
                        style={{ width: "100%", background: "#eab308", color: "#0f172a" }}
                        onClick={() => advanceOrderStatus(order.id, "READY")}
                      >
                        🔔 Báo xong món (READY)
                      </button>
                    </div>
                  ))}
              </div>

              {/* CỘT 3: READY */}
              <div className="card">
                <h3 style={{ color: "#a855f7", marginBottom: "1rem" }}>
                  3. SẴN SÀNG GIAO (READY)
                </h3>
                {orders
                  .filter((o) => o.status === "READY")
                  .map((order) => (
                    <div
                      key={order.id}
                      className="card"
                      style={{ marginBottom: "0.85rem", background: "#0f172a" }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <b>Đơn #{order.id}</b>
                        <span className="plate-badge">{order.license_plate}</span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "0.5rem 0" }}>
                        Đang chờ xe khách tiến vào làn...
                      </div>
                      <button
                        className="btn btn-outline"
                        style={{ width: "100%" }}
                        onClick={() => advanceOrderStatus(order.id, "ARRIVED")}
                      >
                        🚗 Khách bấm "Tôi đã đến" (ARRIVED)
                      </button>
                    </div>
                  ))}
              </div>

              {/* CỘT 4: ARRIVED */}
              <div
                className="card"
                style={{ border: "2px solid #22c55e", background: "rgba(34, 197, 94, 0.06)" }}
              >
                <h3 style={{ color: "#22c55e", marginBottom: "1rem" }}>
                  4. XE ĐÃ ĐẾN LÀN (ARRIVED)
                </h3>
                {orders
                  .filter((o) => o.status === "ARRIVED")
                  .map((order) => (
                    <div
                      key={order.id}
                      className="card"
                      style={{
                        marginBottom: "0.85rem",
                        background: "#0f172a",
                        border: "1px solid #22c55e",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <b>Đơn #{order.id}</b>
                        <span className="plate-badge">{order.license_plate}</span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#cbd5e1", margin: "0.5rem 0" }}>
                        Khách: <b>{order.customer_name}</b>
                        <br />
                        Thanh toán: <span style={{ color: "#fb923c" }}>{order.payment_method}</span>
                        <br />
                        Tổng tiền: <b>{order.total_amount.toLocaleString()}đ</b>
                      </div>
                      <button
                        className="btn btn-success"
                        style={{ width: "100%" }}
                        onClick={() => advanceOrderStatus(order.id, "COMPLETED")}
                      >
                        ✅ Giao Món & Hoàn Thành (COMPLETED)
                      </button>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* ==================== TAB 2: DASHBOARD ADMIN ==================== */}
        {activeTab === "admin" && (
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "1.25rem",
                flexWrap: "wrap",
                gap: "1rem",
              }}
            >
              <div>
                <h2>📊 Dashboard Quản Trị Viên: Thống Kê Chất Lượng & Quản Lý Nhân Sự</h2>
                <p style={{ color: "#94a3b8", fontSize: "0.9rem" }}>
                  Dữ liệu lấy trực tiếp từ <b>feedback-service (feedback_db)</b> và <b>auth-service (auth_db)</b>.
                </p>
              </div>

              <div style={{ display: "flex", gap: "0.65rem", alignItems: "center" }}>
                <span>Chọn cửa hàng:</span>
                <select
                  className="select"
                  style={{ width: "220px", marginTop: 0 }}
                  value={selectedStation}
                  onChange={(e) => setSelectedStation(Number(e.target.value))}
                >
                  <option value={1}>Trạm #1 - Drive-Thru Quận 1</option>
                  <option value={2}>Trạm #2 - Drive-Thru Quận 7</option>
                </select>
                <button className="btn btn-outline" onClick={() => fetchFeedbackData(selectedStation)}>
                  🔄 Làm mới
                </button>
              </div>
            </div>

            {/* THẺ THỐNG KÊ TỔNG QUAN */}
            <div className="grid-4" style={{ marginBottom: "1.5rem" }}>
              <div className="card">
                <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Điểm Trung Bình Cửa Hàng</div>
                <div className="stat-value" style={{ color: "#eab308" }}>
                  {stats.average_rating} / 5.0 ⭐
                </div>
              </div>
              <div className="card">
                <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Tổng Lượt Đánh Giá</div>
                <div className="stat-value" style={{ color: "#3b82f6" }}>
                  {stats.total_reviews} lượt
                </div>
              </div>
              <div className="card">
                <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Cảnh Báo Tiêu Cực (1–2 Sao)</div>
                <div className="stat-value" style={{ color: "#ef4444" }}>
                  {stats.negative_reviews.length} đơn
                </div>
              </div>
              <div className="card">
                <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Đánh Giá Hài Lòng (4–5 Sao)</div>
                <div className="stat-value" style={{ color: "#22c55e" }}>
                  {(stats.rating_breakdown?.[5] || 0) + (stats.rating_breakdown?.[4] || 0)} đơn
                </div>
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: "1.5rem" }}>
              {/* BIỂU ĐỒ PHÂN BỔ SAO */}
              <div className="card">
                <h3 style={{ marginBottom: "1rem" }}>📈 Phân Bổ Số Sao (Trạm #{selectedStation})</h3>
                {[5, 4, 3, 2, 1].map((star) => {
                  const count = stats.rating_breakdown?.[star] || 0;
                  const percent =
                    stats.total_reviews > 0 ? Math.round((count / stats.total_reviews) * 100) : 0;
                  return (
                    <div
                      key={star}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.75rem",
                        marginBottom: "0.75rem",
                      }}
                    >
                      <span style={{ width: "65px", fontWeight: 700 }}>{star} Sao ⭐</span>
                      <div
                        style={{
                          flex: 1,
                          height: "12px",
                          background: "#0f172a",
                          borderRadius: "999px",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${percent}%`,
                            height: "100%",
                            background: star <= 2 ? "#ef4444" : star === 3 ? "#eab308" : "#22c55e",
                          }}
                        />
                      </div>
                      <span style={{ width: "80px", textAlign: "right", fontSize: "0.85rem" }}>
                        {count} ({percent}%)
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* DANH SÁCH GÓP Ý TIÊU CỰC CẦN XỬ LÝ */}
              <div className="card" style={{ borderColor: "rgba(239, 68, 68, 0.45)" }}>
                <h3 style={{ color: "#f87171", marginBottom: "1rem" }}>
                  🚨 Danh Sách Góp Ý Tiêu Cực (1–2 Sao) Cần Khắc Phục
                </h3>
                {stats.negative_reviews.length === 0 ? (
                  <p style={{ color: "#94a3b8" }}>Chưa có phản hồi tiêu cực nào tại cửa hàng này.</p>
                ) : (
                  stats.negative_reviews.map((rev) => (
                    <div
                      key={rev.id}
                      style={{
                        padding: "0.85rem",
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        borderRadius: "0.5rem",
                        marginBottom: "0.75rem",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <b>
                          Đơn #{rev.order_id} — {"⭐".repeat(rev.rating)} ({rev.rating}/5)
                        </b>
                        <span className="badge" style={{ background: "#334155" }}>
                          Nguồn: {rev.source?.toUpperCase() || "WEB"}
                        </span>
                      </div>
                      <div style={{ marginTop: "0.4rem", color: "#fecaca" }}>
                        Lý do khách báo: <b>"{rev.comment}"</b>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* QUẢN LÝ NHÂN VIÊN TRẠM */}
            <div className="grid-2">
              <div className="card">
                <h3 style={{ marginBottom: "1rem" }}>➕ Tạo Tài Khoản Nhân Viên Trạm (auth-service)</h3>
                <form onSubmit={handleCreateStaff}>
                  <div className="form-group">
                    <label>Email nhân viên</label>
                    <input
                      className="input"
                      type="email"
                      required
                      placeholder="staff3@drivethru.vn"
                      value={newStaff.email}
                      onChange={(e) => setNewStaff({ ...newStaff, email: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Họ và tên nhân viên</label>
                    <input
                      className="input"
                      type="text"
                      required
                      placeholder="Nguyễn Văn C"
                      value={newStaff.full_name}
                      onChange={(e) => setNewStaff({ ...newStaff, full_name: e.target.value })}
                    />
                  </div>
                  <div className="grid-2">
                    <div className="form-group">
                      <label>Mật khẩu khởi tạo</label>
                      <input
                        className="input"
                        type="text"
                        required
                        value={newStaff.password}
                        onChange={(e) => setNewStaff({ ...newStaff, password: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Phân công Cửa hàng (station_id)</label>
                      <select
                        className="select"
                        value={newStaff.station_id}
                        onChange={(e) =>
                          setNewStaff({ ...newStaff, station_id: Number(e.target.value) })
                        }
                      >
                        <option value={1}>Trạm #1 - CN Quận 1</option>
                        <option value={2}>Trạm #2 - CN Quận 7</option>
                        <option value={3}>Trạm #3 - CN Thủ Đức</option>
                      </select>
                    </div>
                  </div>
                  <button className="btn btn-primary" type="submit" style={{ width: "100%" }}>
                    Tạo Tài Khoản Nhân Viên
                  </button>
                  {staffMsg && (
                    <div style={{ marginTop: "0.75rem", fontSize: "0.9rem" }}>{staffMsg}</div>
                  )}
                </form>
              </div>

              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
                  <h3>👥 Danh Sách Nhân Viên Các Cửa Hàng</h3>
                  <button className="btn btn-outline" onClick={fetchStaffList}>
                    Tải lại
                  </button>
                </div>
                {staffList.length === 0 ? (
                  <p style={{ color: "#94a3b8" }}>
                    Hãy bấm nút <b>"👑 Admin"</b> trên thanh công cụ để xem và quản lý nhân viên.
                  </p>
                ) : (
                  staffList.map((st) => (
                    <div
                      key={st.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.75rem",
                        background: "#0f172a",
                        borderRadius: "0.5rem",
                        marginBottom: "0.6rem",
                      }}
                    >
                      <div>
                        <b>{st.full_name}</b> ({st.email})
                        <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                          Phụ trách: <b>Trạm #{st.station_id}</b> | Trạng thái:{" "}
                          <span style={{ color: st.is_active ? "#22c55e" : "#ef4444" }}>
                            {st.is_active ? "Đang hoạt động" : "Đã khóa"}
                          </span>
                        </div>
                      </div>
                      <button
                        className="btn btn-outline"
                        onClick={() => handleToggleStaff(st.id)}
                      >
                        {st.is_active ? "Khóa" : "Mở khóa"}
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* ==================== TAB 3: KHÁCH ĐÁNH GIÁ & TELEGRAM ==================== */}
        {activeTab === "customer" && (
          <div className="grid-2">
            {/* GỬI ĐÁNH GIÁ ĐƠN HÀNG */}
            <div className="card">
              <h3 style={{ marginBottom: "0.75rem" }}>⭐ Đánh Giá Đơn Hàng Đã Hoàn Thành</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.88rem", marginBottom: "1rem" }}>
                Nghiệp vụ: Đánh giá từ 1–5 sao. Nếu chọn <b>1 hoặc 2 sao</b>, hệ thống bắt buộc phải nhập lý do góp ý và tự động bắn cảnh báo về Telegram của Quản lý.
              </p>
              <form onSubmit={handleReviewSubmit}>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Mã đơn hàng (order_id)</label>
                    <input
                      className="input"
                      type="number"
                      required
                      value={reviewForm.order_id}
                      onChange={(e) =>
                        setReviewForm({ ...reviewForm, order_id: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label>Cửa hàng phục vụ (station_id)</label>
                    <select
                      className="select"
                      value={reviewForm.station_id}
                      onChange={(e) =>
                        setReviewForm({ ...reviewForm, station_id: Number(e.target.value) })
                      }
                    >
                      <option value={1}>Trạm #1 - CN Quận 1</option>
                      <option value={2}>Trạm #2 - CN Quận 7</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label>Mức độ hài lòng (Chọn số sao)</label>
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                    {[1, 2, 3, 4, 5].map((num) => (
                      <button
                        type="button"
                        key={num}
                        className={`btn ${
                          reviewForm.rating === num ? "btn-primary" : "btn-outline"
                        }`}
                        onClick={() => setReviewForm({ ...reviewForm, rating: num })}
                      >
                        {num} ⭐
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label>
                    Nội dung nhận xét{" "}
                    {reviewForm.rating <= 2 && (
                      <span style={{ color: "#ef4444" }}>(* Bắt buộc khi chấm 1-2 sao)</span>
                    )}
                  </label>
                  <textarea
                    className="textarea"
                    rows={3}
                    placeholder={
                      reviewForm.rating <= 2
                        ? "Vui lòng cho biết lý do bạn chưa hài lòng để cửa hàng khắc phục..."
                        : "Chia sẻ trải nghiệm của bạn (không bắt buộc)..."
                    }
                    value={reviewForm.comment}
                    onChange={(e) => setReviewForm({ ...reviewForm, comment: e.target.value })}
                  />
                </div>

                <button className="btn btn-primary" type="submit" style={{ width: "100%" }}>
                  Gửi Đánh Giá Dịch Vụ
                </button>
                {reviewMsg && (
                  <div style={{ marginTop: "0.85rem", fontWeight: 600 }}>{reviewMsg}</div>
                )}
              </form>
            </div>

            {/* KẾT NỐI TELEGRAM BOT */}
            <div className="card">
              <h3 style={{ marginBottom: "0.75rem" }}>🤖 Kết Nối Tài Khoản Với Telegram Bot</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.88rem", marginBottom: "1rem" }}>
                Khi bấm nút bên dưới, <b>auth-service</b> sẽ sinh ra một mã liên kết dùng 1 lần (One-time Link Token). Khi mở Telegram và bấm <b>Start</b>, Bot Java sẽ gọi ngược về <b>auth-service</b> để gắn <code>telegram_chat_id</code> vào tài khoản của bạn.
              </p>

              <button
                className="btn btn-primary"
                onClick={handleGetTelegramLink}
                style={{ width: "100%", marginBottom: "1rem" }}
              >
                🔗 Tạo Link Liên Kết Telegram Ngay
              </button>

              {telegramLink && (
                <div
                  style={{
                    padding: "1rem",
                    background: "#0f172a",
                    border: "1px solid #3b82f6",
                    borderRadius: "0.6rem",
                  }}
                >
                  <div style={{ fontSize: "0.85rem", color: "#93c5fd" }}>
                    Mã Token một lần của bạn: <b>{telegramLink.link_token}</b>
                  </div>
                  <div style={{ margin: "0.65rem 0" }}>
                    👉{" "}
                    <a
                      href={telegramLink.telegram_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "#38bdf8", fontWeight: 700 }}
                    >
                      {telegramLink.telegram_url}
                    </a>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                    (Hoặc gõ trực tiếp trong Bot Telegram: <code>/start {telegramLink.link_token}</code>)
                  </div>
                </div>
              )}

              <div style={{ marginTop: "1.5rem" }}>
                <h4 style={{ marginBottom: "0.6rem" }}>📋 Đánh Giá Gần Đây Tại Trạm #{selectedStation}</h4>
                {allReviews.slice(0, 4).map((r) => (
                  <div
                    key={r.id}
                    style={{
                      padding: "0.65rem",
                      background: "#0f172a",
                      borderRadius: "0.5rem",
                      marginBottom: "0.5rem",
                      fontSize: "0.85rem",
                    }}
                  >
                    <b>Đơn #{r.order_id}</b> — {"⭐".repeat(r.rating)} ({r.source})
                    <div style={{ color: "#cbd5e1", marginTop: "0.2rem" }}>
                      {r.comment || "(Không có bình luận)"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ==================== TAB 4: ĐĂNG NHẬP / ĐĂNG KÝ ==================== */}
        {activeTab === "login" && (
          <div className="card" style={{ maxWidth: "480px", margin: "0 auto" }}>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.25rem" }}>
              <button
                className={`btn ${authMode === "login" ? "btn-primary" : "btn-outline"}`}
                style={{ flex: 1 }}
                onClick={() => setAuthMode("login")}
              >
                Đăng Nhập
              </button>
              <button
                className={`btn ${authMode === "register" ? "btn-primary" : "btn-outline"}`}
                style={{ flex: 1 }}
                onClick={() => setAuthMode("register")}
              >
                Đăng Ký Khách Hàng
              </button>
            </div>

            <form onSubmit={handleAuthSubmit}>
              {authMode === "register" && (
                <>
                  <div className="form-group">
                    <label>Họ và tên</label>
                    <input
                      className="input"
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Số điện thoại</label>
                    <input
                      className="input"
                      type="text"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                  </div>
                </>
              )}

              <div className="form-group">
                <label>Email</label>
                <input
                  className="input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Mật khẩu</label>
                <input
                  className="input"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <button className="btn btn-primary" type="submit" style={{ width: "100%" }}>
                {authMode === "login" ? "Đăng Nhập Nhận JWT" : "Tạo Tài Khoản Mới"}
              </button>

              {authMsg && <div style={{ marginTop: "0.85rem" }}>{authMsg}</div>}
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

