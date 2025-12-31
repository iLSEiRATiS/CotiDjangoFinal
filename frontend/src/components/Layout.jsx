import { Container } from 'react-bootstrap';
import Header from './Header';
import Footer from './Footer';

const Layout = ({ children }) => (
  <div className="d-flex flex-column min-vh-100">
    <Header />
    <Container as="main" className="my-4 flex-grow-1" role="main">
      {children}
    </Container>
    <Footer />
  </div>
);

export default Layout;
