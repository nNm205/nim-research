import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import DashboardLayout from "../components/layout/DashboardLayout";
import {
  Beaker,
  BarChart3,
  BookOpen,
  Sparkles,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";

const HomePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Nếu user đã đăng nhập, hiển thị dashboard
  if (user) {
    return (
      <DashboardLayout>
        <div className="space-y-8">
          {/* Welcome Section */}
          <div className="bg-gradient-to-r from-teal-50 to-emerald-50 rounded-2xl border border-teal-200 p-8">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-3xl font-bold text-slate-900 mb-2">
                  Chào mừng trở lại, {user?.full_name?.split(" ")[0]}! 👋
                </h1>
                <p className="text-slate-600 text-lg">
                  Sẵn sàng khám phá những tính năng mới và tiếp tục công việc nghiên cứu của bạn
                </p>
              </div>
              <Sparkles className="w-12 h-12 text-teal-600 flex-shrink-0" />
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <StatCard
              title="Dự án hoạt động"
              value="5"
              icon={Beaker}
              color="teal"
            />
            <StatCard
              title="Báo cáo gần đây"
              value="12"
              icon={BarChart3}
              color="emerald"
            />
            <StatCard
              title="Tài liệu"
              value="28"
              icon={BookOpen}
              color="slate"
            />
          </div>

          {/* Features Grid */}
          <div>
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Tính năng chính</h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {features.map((feature, idx) => (
                <FeatureCard key={idx} feature={feature} />
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Bắt đầu nhanh</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <QuickActionCard
                title="Tạo dự án mới"
                description="Bắt đầu một dự án nghiên cứu mới với AI agents"
                icon={Beaker}
                onClick={() => navigate("/projects")}
              />
              <QuickActionCard
                title="Tải lên tài liệu"
                description="Thêm tài liệu để phân tích và nghiên cứu"
                icon={BookOpen}
                onClick={() => navigate("/documents")}
              />
              <QuickActionCard
                title="Xem báo cáo"
                description="Kiểm tra các báo cáo đã tạo gần đây"
                icon={BarChart3}
                onClick={() => navigate("/reports")}
              />
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // Landing page cho user chưa đăng nhập
  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-white to-emerald-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">N</span>
              </div>
              <span className="text-xl font-bold text-slate-900">NIM Research</span>
            </div>

            <nav className="hidden md:flex items-center space-x-8">
              <a href="#features" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Tính năng
              </a>
              <a href="#how-it-works" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Cách hoạt động
              </a>
              <a href="#benefits" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Lợi ích
              </a>
            </nav>

            <div className="flex items-center space-x-3">
              <Link
                to="/login"
                className="text-slate-700 hover:text-slate-900 px-4 py-2 text-sm font-medium transition-colors"
              >
                Đăng nhập
              </Link>
              <Link
                to="/register"
                className="bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-md hover:shadow-lg"
              >
                Đăng ký miễn phí
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
        <div className="text-center max-w-3xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-bold text-slate-900 mb-6 leading-tight">
            Nghiên cứu thông minh với
            <span className="bg-gradient-to-r from-teal-600 to-emerald-600 bg-clip-text text-transparent"> AI Agents</span>
          </h1>

          <p className="text-xl text-slate-600 mb-8 leading-relaxed">
            Tự động hóa quy trình nghiên cứu, phân tích dữ liệu và tạo báo cáo chuyên nghiệp 
            với sức mạnh của Multi-Agent AI System
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/register"
              className="w-full sm:w-auto bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white px-8 py-4 rounded-xl text-base font-semibold transition-all hover:shadow-lg hover:scale-105 shadow-md flex items-center justify-center gap-2"
            >
              Bắt đầu miễn phí <ArrowRight className="w-5 h-5" />
            </Link>
            <a
              href="#how-it-works"
              className="w-full sm:w-auto border-2 border-slate-300 hover:border-teal-400 text-slate-700 hover:text-teal-600 px-8 py-4 rounded-xl text-base font-semibold transition-all hover:bg-teal-50"
            >
              Xem demo
            </a>
          </div>
        </div>

        {/* Hero Image/Illustration */}
        <div className="mt-16 relative">
          <div className="bg-gradient-to-br from-teal-100 to-emerald-100 rounded-2xl p-8 shadow-xl border border-teal-200">
            <div className="bg-white rounded-xl shadow-lg p-6 space-y-4">
              <div className="flex items-center space-x-3">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>
              <div className="space-y-3">
                <div className="h-4 bg-slate-200 rounded w-3/4 animate-pulse"></div>
                <div className="h-4 bg-slate-200 rounded w-full animate-pulse"></div>
                <div className="h-4 bg-slate-200 rounded w-5/6 animate-pulse"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
            Tính năng nổi bật
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Hệ thống AI đa tác vụ giúp bạn nghiên cứu và phân tích hiệu quả hơn
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {landingFeatures.map((feature, idx) => (
            <div
              key={idx}
              className="bg-white rounded-2xl p-6 border border-slate-200 hover:shadow-lg hover:border-teal-300 transition-all group"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-teal-500 to-emerald-500 rounded-lg flex items-center justify-center mb-4 group-hover:shadow-lg transition-shadow">
                <span className="text-2xl">{feature.icon}</span>
              </div>
              <h3 className="text-xl font-semibold text-slate-900 mb-2">
                {feature.title}
              </h3>
              <p className="text-slate-600 leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="bg-slate-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Cách hoạt động
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Quy trình đơn giản, kết quả chuyên nghiệp
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {steps.map((step, idx) => (
              <div key={idx} className="relative">
                <div className="bg-white rounded-2xl p-6 border border-slate-200 h-full shadow-sm hover:shadow-md transition-shadow">
                  <div className="w-10 h-10 bg-gradient-to-br from-teal-600 to-emerald-600 text-white rounded-full flex items-center justify-center font-bold mb-4">
                    {idx + 1}
                  </div>
                  <h3 className="text-xl font-semibold text-slate-900 mb-2">
                    {step.title}
                  </h3>
                  <p className="text-slate-600">
                    {step.description}
                  </p>
                </div>
                {idx < steps.length - 1 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 transform -translate-y-1/2">
                    <svg className="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section id="benefits" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
            Tại sao chọn NIM Research?
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Giải pháp toàn diện cho nghiên cứu học thuật hiện đại
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {benefits.map((benefit, idx) => (
            <div key={idx} className="flex gap-4 p-6 bg-white rounded-2xl border border-slate-200 hover:shadow-md transition-shadow">
              <CheckCircle2 className="w-6 h-6 text-teal-600 flex-shrink-0 mt-1" />
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">
                  {benefit.title}
                </h3>
                <p className="text-slate-600">
                  {benefit.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="bg-gradient-to-br from-teal-600 to-emerald-600 rounded-2xl p-12 text-center text-white shadow-xl">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Sẵn sàng bắt đầu?
          </h2>
          <p className="text-xl text-teal-100 mb-8 max-w-2xl mx-auto">
            Tham gia cùng hàng nghìn nhà nghiên cứu đang sử dụng AI để tăng tốc công việc
          </p>
          <Link
            to="/register"
            className="inline-block bg-white text-teal-600 px-8 py-4 rounded-xl text-base font-semibold hover:bg-slate-100 transition-all hover:scale-105 shadow-lg hover:shadow-xl"
          >
            Đăng ký miễn phí ngay
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-lg">N</span>
                </div>
                <span className="text-xl font-bold text-slate-900">NIM-ENG</span>
              </div>
              <p className="text-slate-600 text-sm">
                Hệ thống AI Research & Analysis thông minh
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-4">Sản phẩm</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="#features" className="hover:text-slate-900 transition-colors">Tính năng</a></li>
                <li><a href="#how-it-works" className="hover:text-slate-900 transition-colors">Cách hoạt động</a></li>
                <li><a href="#benefits" className="hover:text-slate-900 transition-colors">Lợi ích</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-4">Công ty</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="#" className="hover:text-slate-900 transition-colors">Về chúng tôi</a></li>
                <li><a href="#" className="hover:text-slate-900 transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-slate-900 transition-colors">Liên hệ</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-4">Pháp lý</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="#" className="hover:text-slate-900 transition-colors">Điều khoản</a></li>
                <li><a href="#" className="hover:text-slate-900 transition-colors">Bảo mật</a></li>
                <li><a href="#" className="hover:text-slate-900 transition-colors">Cookie</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-slate-200 mt-8 pt-8 text-center text-sm text-slate-600">
            © 2024 NIM-ENG. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

const features = [
  {
    icon: "🔍",
    title: "Research Agent",
    description: "Tự động thu thập và tổng hợp thông tin từ nhiều nguồn đáng tin cậy"
  },
  {
    icon: "📊",
    title: "Analysis Agent",
    description: "Phân tích dữ liệu sâu với machine learning và statistical methods"
  },
  {
    icon: "📝",
    title: "Synthesis Agent",
    description: "Tổng hợp và tạo báo cáo chuyên nghiệp từ kết quả nghiên cứu"
  },
  {
    icon: "🤖",
    title: "Multi-Agent System",
    description: "Các AI agents phối hợp làm việc để đạt hiệu quả tối ưu"
  },
  {
    icon: "⚡",
    title: "Real-time Processing",
    description: "Xử lý và cập nhật kết quả theo thời gian thực"
  }
];

const landingFeatures = [
  {
    icon: "🔍",
    title: "Research Agent",
    description: "Tự động thu thập và tổng hợp thông tin từ nhiều nguồn đáng tin cậy"
  },
  {
    icon: "📊",
    title: "Analysis Agent",
    description: "Phân tích dữ liệu sâu với machine learning và statistical methods"
  },
  {
    icon: "📝",
    title: "Synthesis Agent",
    description: "Tổng hợp và tạo báo cáo chuyên nghiệp từ kết quả nghiên cứu"
  },
  {
    icon: "🤖",
    title: "Multi-Agent System",
    description: "Các AI agents phối hợp làm việc để đạt hiệu quả tối ưu"
  },
  {
    icon: "⚡",
    title: "Real-time Processing",
    description: "Xử lý và cập nhật kết quả theo thời gian thực"
  }
];

const steps = [
  {
    title: "Upload tài liệu",
    description: "Tải lên các tài liệu, dữ liệu cần nghiên cứu và phân tích"
  },
  {
    title: "AI xử lý",
    description: "Hệ thống AI agents tự động phân tích và tổng hợp thông tin"
  },
  {
    title: "Nhận báo cáo",
    description: "Nhận báo cáo chi tiết, insights và recommendations"
  }
];

const benefits = [
  {
    title: "Tiết kiệm thời gian",
    description: "Tự động hóa các tác vụ lặp lại, giúp bạn tập trung vào phân tích sâu"
  },
  {
    title: "Chất lượng cao",
    description: "Báo cáo chuyên nghiệp với phân tích chi tiết và insights sâu sắc"
  },
  {
    title: "Dễ sử dụng",
    description: "Giao diện trực quan, không cần kỹ năng kỹ thuật cao"
  },
  {
    title: "Bảo mật dữ liệu",
    description: "Mã hóa end-to-end, tuân thủ các tiêu chuẩn bảo mật quốc tế"
  },
  {
    title: "Hỗ trợ 24/7",
    description: "Đội ngũ hỗ trợ sẵn sàng giúp đỡ bất cứ lúc nào"
  },
  {
    title: "Tích hợp dễ dàng",
    description: "API mạnh mẽ, tích hợp với các công cụ yêu thích của bạn"
  }
];

// Components cho dashboard
const StatCard = ({ title, value, icon: Icon, color }) => {
  const colorClasses = {
    teal: "from-teal-50 to-teal-100",
    emerald: "from-emerald-50 to-emerald-100",
    slate: "from-slate-50 to-slate-100",
  };

  const iconColorClasses = {
    teal: "text-teal-600",
    emerald: "text-emerald-600",
    slate: "text-slate-600",
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-slate-300 transition-all group">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-600 mb-2">{title}</p>
          <p className="text-3xl font-bold text-slate-900">{value}</p>
        </div>
        <div
          className={`w-16 h-16 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center group-hover:shadow-md transition-all`}
        >
          <Icon className={`w-8 h-8 ${iconColorClasses[color]}`} />
        </div>
      </div>
    </div>
  );
};

const FeatureCard = ({ feature }) => {
  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 hover:shadow-lg hover:border-teal-300 transition-all group">
      <div className="w-12 h-12 bg-gradient-to-br from-teal-500 to-emerald-500 rounded-lg flex items-center justify-center mb-4 group-hover:shadow-lg transition-shadow">
        <span className="text-2xl">{feature.icon}</span>
      </div>
      <h3 className="text-xl font-semibold text-slate-900 mb-2">
        {feature.title}
      </h3>
      <p className="text-slate-600 leading-relaxed">
        {feature.description}
      </p>
    </div>
  );
};

const QuickActionCard = ({ title, description, icon: Icon, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="bg-white rounded-2xl border border-slate-200 p-6 text-left hover:shadow-lg hover:border-teal-300 transition-all group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="w-12 h-12 bg-gradient-to-br from-teal-500 to-emerald-500 rounded-lg flex items-center justify-center group-hover:shadow-lg transition-shadow">
          <Icon className="w-6 h-6 text-white" />
        </div>
        <ArrowRight className="w-5 h-5 text-teal-600 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2 group-hover:text-teal-600 transition-colors">
        {title}
      </h3>
      <p className="text-slate-600 text-sm">
        {description}
      </p>
    </button>
  );
};
export default HomePage;
