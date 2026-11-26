import { useQuery } from "@tanstack/react-query";
import App from "../App";
import { fetchCollective2Access } from "./api";

export default function Collective2App() {
  const access = useQuery({
    queryKey: ["collective2-access"],
    queryFn: fetchCollective2Access,
    retry: false,
  });

  if (access.isPending) {
    return <p role="status">접근 권한을 확인하는 중입니다.</p>;
  }
  if (!access.isSuccess) {
    return <p role="alert">아직 공개하지 않은 기능입니다.</p>;
  }
  return <App combinedPreview />;
}
