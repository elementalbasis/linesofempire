import numpy as np
import rasterio

from rasterio.warp import transform as transform_coords

from common import lonlat_to_xyz


class GeoRaster:
    def __init__(self, filename, grid_step=16):
        self.filename = filename

        with rasterio.open(filename) as src:
            self.crs = src.crs
            self.transform = src.transform
            self.width = src.width
            self.height = src.height

            self.image = self._read_rgba(src)
            self.vertices = self._build_mesh(
                src,
                grid_step,
            )

    def _read_rgba(self, src):
        data = src.read()

        if data.shape[0] >= 3:
            rgb = np.moveaxis(
                data[:3],
                0,
                -1,
            )

            rgb = rgb.astype(np.float32)

            # This assumes 8-bit-ish imagery for now.
            if rgb.max() > 255:
                rgb *= 255.0 / rgb.max()

            rgb = np.clip(
                rgb,
                0,
                255,
            ).astype(np.uint8)

        else:
            gray = data[0].astype(np.float32)

            if gray.max() > 255:
                gray *= 255.0 / gray.max()

            gray = np.clip(
                gray,
                0,
                255,
            ).astype(np.uint8)

            rgb = np.repeat(
                gray[..., None],
                3,
                axis=2,
            )

        if data.shape[0] >= 4:
            alpha = data[3].astype(np.uint8)
        else:
            alpha = np.full(
                (src.height, src.width),
                255,
                dtype=np.uint8,
            )

        if src.nodata is not None:
            mask = src.read(1) == src.nodata
            alpha[mask] = 0

        return np.dstack((
            rgb,
            alpha,
        ))

    def _build_mesh(self, src, step):
        rows = list(range(
            0,
            src.height,
            step,
        ))

        cols = list(range(
            0,
            src.width,
            step,
        ))

        # Always include the last row/column.
        if rows[-1] != src.height - 1:
            rows.append(src.height - 1)

        if cols[-1] != src.width - 1:
            cols.append(src.width - 1)

        # --------------------------------------------------
        # Obtain source-CRS coordinates for grid vertices.
        # --------------------------------------------------

        xs = []
        ys = []
        rc = []

        for row in rows:
            for col in cols:
                x, y = rasterio.transform.xy(
                    src.transform,
                    row,
                    col,
                    offset='center',
                )

                xs.append(x)
                ys.append(y)
                rc.append((row, col))

        # --------------------------------------------------
        # Transform whatever CRS the TIFF uses to WGS84.
        # --------------------------------------------------

        lon, lat = transform_coords(
            src.crs,
            'EPSG:4326',
            xs,
            ys,
        )

        points = {}

        for (row, col), lo, la in zip(
                rc,
                lon,
                lat,
                ):
            xyz = lonlat_to_xyz(
                lo,
                la,
            )

            u = col / (src.width - 1)
            v = row / (src.height - 1)

            points[(row, col)] = (
                *xyz,
                u,
                v,
            )

        # --------------------------------------------------
        # Two triangles per grid cell.
        # --------------------------------------------------

        vertices = []

        for r0, r1 in zip(
                rows[:-1],
                rows[1:],
                ):
            for c0, c1 in zip(
                    cols[:-1],
                    cols[1:],
                    ):

                tl = points[(r0, c0)]
                tr = points[(r0, c1)]
                bl = points[(r1, c0)]
                br = points[(r1, c1)]

                vertices.extend([
                    tl,
                    bl,
                    br,

                    tl,
                    br,
                    tr,
                ])

        return np.asarray(
            vertices,
            dtype='f4',
        )
