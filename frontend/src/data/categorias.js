// Estructura jerárquica para el mega-dropdown
export const CATEGORIAS = [
  {
    nombre: 'Cotillón',
    subcategorias: [
      { nombre: 'Velas', hijos: [
        'Velas con Palito',
        'Velas Importadas',
        'Bengalas',
        'Velas con Luz',
        'Velas Estrellita'
      ]},
      'Vinchas y Coronas',
      'Gorros y Sombreros',
      'Antifaces',
      'Carioca'
    ]
  },
  {
    nombre: 'Globos y Piñatas',
    subcategorias: [
      'Número Metalizados',
      'Globos con Forma',
      'Set de Globos',
      { nombre: '9 Pulgadas', hijos: ['Perlado'] }
    ]
  }
];
