import { useEffect, useState } from "react";
import { Layout, Typography, Row, Col } from "antd";
import ScheduleForm from "../components/ScheduleForm";
import VideoTable from "../components/VideoTable";
import { translations } from "../i18n/ru";
import { videosApi } from "../api";

const { Header, Content } = Layout;
const { Title } = Typography;

export default function HomePage() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadVideos = async () => {
    setLoading(true);
    try {
      const response = await videosApi.list();
      setVideos(response.data);
    } catch (error) {
      console.error("Error loading videos:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVideos();
  }, []);

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Header
        style={{
          background: "#001529",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
        }}
      >
        <Title level={3} style={{ color: "white", margin: 0 }}>
          {translations.app.title}
        </Title>
        <span style={{ color: "#fff", marginLeft: 16, opacity: 0.7 }}>
          {translations.app.subtitle}
        </span>
      </Header>
      <Content style={{ padding: "24px" }}>
        <Row gutter={[0, 16]}>
          <Col span={24}>
            <ScheduleForm onLoadComplete={loadVideos} />
          </Col>
          <Col span={24}>
            <VideoTable
              videos={videos}
              loading={loading}
              onRefresh={loadVideos}
            />
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
