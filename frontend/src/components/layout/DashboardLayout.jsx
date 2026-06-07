import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import NotificationCenter from "./NotificationCenter";
import {
  Home,
  Folder,
  FileText,
  BarChart3,
  ClipboardList,
  LogOut,
  Settings,
  User,
  ChevronDown,
  ChevronLeft,
  ChevronRight
} from "lucide-react";

const DashboardLayout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full bg-white border-r border-slate-200 transition-all duration-300 z-40 shadow-sm ${
          sidebarOpen ? "w-64" : "w-20"
        }`}
      >
        {/* Logo */}
        <div className="h-20 flex items-center justify-between px-4 border-b border-slate-200">
          {sidebarOpen ? (
            <Link to="/dashboard" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
              <div className="w-10 h-10 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-lg">N</span>
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold text-slate-900 leading-none">NIM</span>
                <span className="text-xs text-slate-500 font-semibold">Research</span>
              </div>
            </Link>
          ) : (
            <Link
              to="/dashboard"
              className="flex justify-center w-full hover:opacity-80 transition-opacity"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-lg">N</span>
              </div>
            </Link>
          )}
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2">
          {menuItems.map((item) => (
            <NavItem
              key={item.path}
              {...item}
              isActive={location.pathname === item.path}
              collapsed={!sidebarOpen}
            />
          ))}
        </nav>

        {/* Toggle Button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute -right-3 top-20 w-6 h-6 bg-white border border-slate-200 rounded-full flex items-center justify-center hover:bg-slate-50 hover:border-slate-300 transition-all shadow-md"
          title={sidebarOpen ? "Ẩn thanh bên" : "Hiển thị thanh bên"}
        >
          {sidebarOpen ? (
            <ChevronLeft className="w-3 h-3 text-slate-600" />
          ) : (
            <ChevronRight className="w-3 h-3 text-slate-600" />
          )}
        </button>

        {/* Footer - User Info Minimal */}
        {sidebarOpen && (
          <div className="absolute bottom-4 left-4 right-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-xs text-slate-600">Logged in as</p>
            <p className="text-sm font-semibold text-slate-900 truncate">
              {user?.full_name || "User"}
            </p>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <div
        className={`transition-all duration-300 ${
          sidebarOpen ? "ml-64" : "ml-20"
        }`}
      >
        {/* Header */}
        <header className="h-20 bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
          <div className="h-full px-8 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-slate-900">
                {menuItems.find((item) => item.path === location.pathname)
                  ?.label || "Dashboard"}
              </h2>
            </div>

            <div className="flex items-center gap-4">
              {/* Notifications */}
              <NotificationCenter />

              {/* Divider */}
              <div className="w-px h-6 bg-slate-200"></div>

              {/* User Menu */}
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-3 p-2 hover:bg-slate-100 rounded-lg transition-colors group"
                >
                  <div className="w-9 h-9 bg-gradient-to-br from-teal-500 to-teal-600 rounded-lg flex items-center justify-center shadow-md group-hover:shadow-lg transition-shadow">
                    <span className="text-white font-bold text-sm">
                      {user?.full_name?.charAt(0).toUpperCase() || "U"}
                    </span>
                  </div>
                  <div className="text-left hidden md:block">
                    <p className="text-sm font-semibold text-slate-900">
                      {user?.full_name || "User"}
                    </p>
                    <p className="text-xs text-slate-500">{user?.email}</p>
                  </div>
                  <ChevronDown
                    className={`w-4 h-4 text-slate-600 transition-transform ${
                      userMenuOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>

                {/* Dropdown Menu */}
                {userMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setUserMenuOpen(false)}
                    ></div>
                    <div className="absolute right-0 mt-3 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-2 z-50">
                      <Link
                        to="/profile"
                        className="flex items-center gap-3 px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 transition-colors group"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        <User className="w-4 h-4 text-slate-400 group-hover:text-teal-600 transition-colors" />
                        <span>Hồ sơ cá nhân</span>
                      </Link>
                      <Link
                        to="/settings"
                        className="flex items-center gap-3 px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 transition-colors group"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        <Settings className="w-4 h-4 text-slate-400 group-hover:text-teal-600 transition-colors" />
                        <span>Cài đặt</span>
                      </Link>
                      <hr className="my-2 border-slate-200" />
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-600 hover:bg-red-50 transition-colors group"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Đăng xuất</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-8">{children}</main>
      </div>
    </div>
  );
};

const NavItem = ({ path, label, icon: Icon, isActive, collapsed }) => {
  return (
    <Link
      to={path}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-all ${
        isActive
          ? "bg-teal-50 text-teal-600 shadow-sm border border-teal-200"
          : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
      } ${collapsed ? "justify-center" : ""}`}
      title={collapsed ? label : ""}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? "text-teal-600" : ""}`} />
      {!collapsed && <span>{label}</span>}
    </Link>
  );
};

const menuItems = [
  {
    path: "/dashboard",
    label: "Tổng quan",
    icon: Home
  },
  {
    path: "/projects",
    label: "Dự án",
    icon: Folder
  },
  {
    path: "/documents",
    label: "Tài liệu",
    icon: FileText
  },
  {
    path: "/analysis",
    label: "Phân tích",
    icon: BarChart3
  },
  {
    path: "/reports",
    label: "Báo cáo",
    icon: ClipboardList
  }
];

export default DashboardLayout;