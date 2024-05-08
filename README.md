# fel_gt
Módulo base para Facturación Electrónica en Guatemala. Genera el DTE a partir de una factura. Para integrar con certificadores, es necesario instalar también el módulo fel del certificador.

- Funciona para la versión 17.0
- El campo de Frases FEL y Adenda FEL en la pestaña Extra de la Compañía ejecutan su contenido como código Python.
- Para agregar frases, se puede hacer fácilmente con la funcion:

```python
frase(tipo=1, escenario=2)
```

Nuestros módulos son de código abierto, licencia BSD 3-clause "New". Así que pueden ser usados por cualquiera, sin excepción.

Aceptamos pull requests y también issues por si encuentran un error con nuestro código.
