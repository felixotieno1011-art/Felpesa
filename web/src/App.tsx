import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import SendMoney from "./pages/SendMoney";
import History from "./pages/History";
import Admin from "./pages/Admin";
import Pay from "./pages/Pay";
import Money from "./pages/Money";
import Pin from "./pages/Pin";
import Airtime from "./pages/Airtime";
import Mpesa from "./pages/Mpesa";

function Protected({ children }: { children: JSX.Element }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/send" element={<SendMoney />} />
        <Route path="/history" element={<History />} />
        <Route path="/pay" element={<Pay />} />
        <Route path="/money" element={<Money />} />
        <Route path="/pin" element={<Pin />} />
        <Route path="/airtime" element={<Airtime />} />
        <Route path="/mpesa" element={<Mpesa />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
