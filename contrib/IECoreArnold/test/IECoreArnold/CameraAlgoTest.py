##########################################################################
#
#  Copyright (c) 2016, Image Engine Design Inc. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#     * Neither the name of Image Engine Design nor the names of any
#       other contributors to this software may be used to endorse or
#       promote products derived from this software without specific prior
#       written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
#  IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
#  THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#  PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##########################################################################

import math
import random
import unittest

import arnold

import IECore
import IECoreScene
import IECoreArnold

import imath

class CameraAlgoTest( unittest.TestCase ) :

	def testConvertPerspective( self ) :

		with IECoreArnold.UniverseBlock( writable = True ) :

			c = IECoreScene.Camera(
				parameters = {
					"projection" : "perspective",
					"focalLength" : 1 / ( 2.0 * math.tan( 0.5 * math.radians( 45 ) ) ),
					"resolution" : imath.V2i( 512 ),
					"aperture" : imath.V2f( 2, 1 )
				}
			)

			n = IECoreArnold.NodeAlgo.convert( c, "testCamera" )
			screenWindow = c.frustum()

			self.assertTrue( arnold.AiNodeEntryGetName( arnold.AiNodeGetNodeEntry( n ) ), "persp_camera" )

			screenWindowMult = math.tan( 0.5 * math.radians( arnold.AiNodeGetFlt( n, "fov" ) ) )

			self.assertAlmostEqual( screenWindowMult * arnold.AiNodeGetVec2( n, "screen_window_min" ).x, screenWindow.min()[0] )
			self.assertAlmostEqual( screenWindowMult * arnold.AiNodeGetVec2( n, "screen_window_min" ).y, screenWindow.min()[1] )
			self.assertAlmostEqual( screenWindowMult * arnold.AiNodeGetVec2( n, "screen_window_max" ).x, screenWindow.max()[0] )
			self.assertAlmostEqual( screenWindowMult * arnold.AiNodeGetVec2( n, "screen_window_max" ).y, screenWindow.max()[1] )

	def testConvertCustomProjection( self ) :

		with IECoreArnold.UniverseBlock( writable = True ) :

			n = IECoreArnold.NodeAlgo.convert(
				IECoreScene.Camera(
					parameters = {
						"projection" : "cyl_camera",
						"horizontal_fov" : 45.0,
						"vertical_fov" : 80.0,
					}
				),
				"testCamera"
			)

			self.assertTrue( arnold.AiNodeEntryGetName( arnold.AiNodeGetNodeEntry( n ) ), "cyl_camera" )
			self.assertEqual( arnold.AiNodeGetFlt( n, "horizontal_fov" ), 45.0 )
			self.assertEqual( arnold.AiNodeGetFlt( n, "vertical_fov" ), 80.0 )

	# This test makes sure that for a camera with no focal length defined, but with a fov, the default
	# focal length calculation on the camera results in getting the same projection in Arnold that we
	# had before.
	def testOldRandomCamera( self ) :

		random.seed( 42 )

		with IECoreArnold.UniverseBlock( writable = True ) :
			for i in range( 40 ):
				resolution = imath.V2i( random.randint( 10, 1000 ), random.randint( 10, 1000 ) )
				pixelAspectRatio = random.uniform( 0.5, 2 )
				screenWindow = imath.Box2f(
							imath.V2f( -random.uniform( 0, 2 ), -random.uniform( 0, 2 ) ),
							imath.V2f(  random.uniform( 0, 2 ), random.uniform( 0, 2 ) )
						)

				screenWindowAspectScale = imath.V2f( 1.0, ( screenWindow.size()[0] / screenWindow.size()[1] ) * ( resolution[1] / float(resolution[0]) ) / pixelAspectRatio )
				screenWindow.setMin( screenWindow.min() * screenWindowAspectScale )
				screenWindow.setMax( screenWindow.max() * screenWindowAspectScale )

				c = IECoreScene.Camera(
					parameters = {
						"projection" : "orthographic" if random.random() > 0.5 else "perspective",
						"projection:fov" : random.uniform( 1, 100 ),
						"clippingPlanes" : imath.V2f( random.uniform( 0.001, 100 ) ) + imath.V2f( 0, random.uniform( 0, 1000 ) ),
						"resolution" : resolution,
						"pixelAspectRatio" : pixelAspectRatio
					}
				)

				if i < 20:
					c.parameters()["screenWindow"] = screenWindow

				n = IECoreArnold.NodeAlgo.convert( c, "testCamera" )

				arnoldType = "persp_camera"
				if c.parameters()["projection"].value == "orthographic":
					arnoldType = "ortho_camera"

				self.assertEqual( arnold.AiNodeEntryGetName( arnold.AiNodeGetNodeEntry( n ) ), arnoldType )

				cortexClip = c.parameters()["clippingPlanes"].value
				self.assertEqual( arnold.AiNodeGetFlt( n, "near_clip" ), cortexClip[0] )
				self.assertEqual( arnold.AiNodeGetFlt( n, "far_clip" ), cortexClip[1] )

				resolution = c.parameters()["resolution"].value
				aspect = c.parameters()["pixelAspectRatio"].value * resolution.x / float(resolution.y)

				if "screenWindow" in c.parameters():
					cortexWindow = c.parameters()["screenWindow"].value
				else:
					if aspect > 1.0:
						cortexWindow = imath.Box2f( imath.V2f( -aspect, -1 ), imath.V2f( aspect, 1 ) )
					else:
						cortexWindow = imath.Box2f( imath.V2f( -1, -1 / aspect ), imath.V2f( 1, 1 / aspect ) )


				if c.parameters()["projection"].value != "orthographic":
					windowScale = math.tan( math.radians( 0.5 * arnold.AiNodeGetFlt( n, "fov" ) ) )
					cortexWindowScale = math.tan( math.radians( 0.5 * c.parameters()["projection:fov"].value ) )
				else:
					windowScale = 1.0
					cortexWindowScale = 1.0


				self.assertAlmostEqual( windowScale * arnold.AiNodeGetVec2( n, "screen_window_min" ).x, cortexWindowScale * cortexWindow.min()[0], places = 4 )
				self.assertAlmostEqual( windowScale * arnold.AiNodeGetVec2( n, "screen_window_min" ).y, cortexWindowScale * cortexWindow.min()[1] * aspect, places = 4 )
				self.assertAlmostEqual( windowScale * arnold.AiNodeGetVec2( n, "screen_window_max" ).x, cortexWindowScale * cortexWindow.max()[0], places = 4 )
				self.assertAlmostEqual( windowScale * arnold.AiNodeGetVec2( n, "screen_window_max" ).y, cortexWindowScale * cortexWindow.max()[1] * aspect, places = 4 )

if __name__ == "__main__":
    unittest.main()
