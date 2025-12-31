// src/App.test.js
import { render, screen } from '@testing-library/react';
import App from './App';

test('renderiza contenido del cotillón', () => {
  render(<App />);
  const text = screen.getByText(/cotillón/i);
  expect(text).toBeInTheDocument();
});
