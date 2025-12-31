import { InputGroup, Form, Button } from 'react-bootstrap';
import { FaSearch } from 'react-icons/fa';

export default function SearchBar({
  value,
  onChange,
  onSubmit = () => {},
  placeholder = 'Buscar...',
  ariaLabel = 'Buscar',
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <Form onSubmit={handleSubmit} role="search">
      <InputGroup>
        <Form.Control
          type="search"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={ariaLabel}
        />
        <Button type="submit" className="btn-search-accent">
          <FaSearch />
        </Button>
      </InputGroup>
    </Form>
  );
}
